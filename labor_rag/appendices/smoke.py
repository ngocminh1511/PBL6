"""Verify the running local API with real data; --chat also uses configured cloud services."""
import argparse
import hashlib

import requests

from .catalog import PROCESSED_DIR, now, write_json


def run(*, chat=False, base="http://127.0.0.1:8000"):
    def get(path):
        r=requests.get(base+path,timeout=20)
        r.raise_for_status()
        return r
    result={"checked_at":now(),"home":get('/').status_code,"data":get('/api/health').json()['data']}
    items=get('/api/appendices?document=09-2020-tt-bldtbxh').json()['items']
    assert len(items)==5
    item=next(a for a in items if a['key']=='2')
    assert get(item['view_url']).status_code==200
    artifact=item['files'][0]
    payload=get(artifact['download_url']).content
    assert hashlib.sha256(payload).hexdigest()==artifact['artifact_id'].split(':',1)[1]
    result['file_hash_verified']=True
    if chat:
        question='Danh mục công việc nhẹ trong Phụ lục II của Thông tư 09/2020/TT-BLĐTBXH gồm những gì?'
        response=requests.post(base+'/api/chat',json={'question':question},timeout=240)
        response.raise_for_status()
        answer=response.json()
        result['chat']=answer
        assert any(e['appendix_id']=='09-2020-tt-bldtbxh:pl2' for e in answer['evidence'])
        for evidence in answer['evidence']:
            if evidence.get('view_url'):
                page=get(evidence['view_url'])
                assert 'highlight' in page.text
        result['citation_view_verified']=True
    write_json(PROCESSED_DIR/'api_smoke_report.json',result)
    return {k:v for k,v in result.items() if k!='chat'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chat',action='store_true')
    args=parser.parse_args()
    print(run(chat=args.chat))
