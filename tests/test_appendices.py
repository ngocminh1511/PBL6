"""Appendix boundaries, provenance, IDs, citations and local file API. No network."""
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from labor_rag.appendices import catalog as storage
from labor_rag.appendices.collect import Collector, decode_flight, public_document
from labor_rag.appendices.extract import normalize_sections, make_chunks, article_links, sanitized
from labor_rag.appendices.runtime import AppendixCatalog
from labor_rag.app.api import create_app
from labor_rag.generation.citation_verify import verify_citations
from labor_rag.ingest.chunk_schema import article_id, part_number
from labor_rag.retrieval.hybrid_retrieve import Evidence


def flight_page(number="09/2020/TT-BLĐTBXH"):
    text="<p>Văn bản tiếng Việt — phụ lục</p>"
    meta={"id":152670,"docNum":number,"documentContent":{"content":"$2b"},"title":"Sửa đổi 09/2020/TT-BLĐTBXH"}
    record="2b:T"+format(len(text.encode()),"x")+","+text+"\n1:"+json.dumps(meta,ensure_ascii=False)+"\n"
    # Split a record across Next.js script chunks.
    return "".join("<script>self.__next_f.push("+json.dumps([1,s],ensure_ascii=False)+")</script>" for s in [record[:25],record[25:]])


def test_public_unicode_records_and_exact_document_number():
    page=flight_page()
    assert "tiếng Việt" in decode_flight(page)["2b"]
    assert public_document(page,"152670","09/2020/TT-BLĐTBXH")[0]["id"]==152670
    with pytest.raises(ValueError,match="mismatch"):
        public_document(flight_page("02/2024/TT-BLĐTBXH"),"152670","09/2020/TT-BLĐTBXH")
    with pytest.raises(ValueError,match="metadata"):
        public_document("<html>Home or access denied</html>","152670","09/2020/TT-BLĐTBXH")


def test_article_ids_do_not_collapse_appendices():
    assert article_id("doc:pl2:p12")=="doc:pl2"
    assert article_id("doc:pl2")=="doc:pl2"
    assert article_id("doc:d2:p12")=="doc:d2"
    assert part_number("doc:pl2")==0


HTML='''<h1>DANH MỤC VỀ VIỆC BAN HÀNH</h1><p>Ban hành kèm theo thông tư</p>
<p>Điều 8. Công việc nhẹ</p><p>Ban hành kèm theo Phụ lục II của thông tư.</p>
<p>Phụ lục I</p><p>________</p><p>MẪU HỢP ĐỒNG LAO ĐỘNG</p><p>Mẫu số 01</p><p>Người khai: …</p>
<p>Phụ lục II</p><p>DANH MỤC CÔNG VIỆC NHẸ</p><p>(Ban hành kèm theo thông tư)</p>
<table onclick="alert(1)"><tr><th>STT</th><th>Nghề</th></tr><tr><td>1</td><td>Biểu diễn nghệ thuật</td></tr></table>'''


def test_boundaries_no_body_no_duplicate_title_keep_table():
    sections=normalize_sections(HTML,"doc")
    assert [s["key"] for s in sections]==["1","2"]
    assert [s["kind"] for s in sections]==["form","reference"]
    assert "Điều 8" not in "".join(s["text"] for s in sections)
    assert "MẪU HỢP ĐỒNG" in sections[0]["title"]
    table=sections[1]["blocks"][-1]
    assert "<table" in table["html"] and "onclick" not in table["html"]
    assert table["rows"][0]["header"] and len(table["rows"])==2
    assert table["rows"][1]["id"] in table["html"]
    assert 'script' not in sanitized('<script>alert(1)</script><p onmouseover="x()">safe<img src=x></p>')
    assert normalize_sections('<p><span>Ph</span><span>ụ lục II</span></p><p>DANH MỤC</p>', 'doc')[0]['key']=='2'


def test_exact_article_mapping_not_same_file_fanout():
    section={"key":"2"}
    common={"target_document":"09/2020/TT-BLĐTBXH","owner_document":"09/2020/TT-BLĐTBXH"}
    refs=[dict(common,canonical_label="2",article="20.2.TT.1.8"),dict(common,canonical_label="3",article="20.2.TT.1.9")]
    links=article_links(section,{"document":"09/2020/TT-BLĐTBXH"},refs)
    assert [r["article_number"] for r in links]==["8"]


def test_table_chunks_repeat_header_and_have_correct_locators():
    rows="".join(f"<tr><td>{i}</td><td>"+"việc nhẹ "*65+"</td></tr>" for i in range(30))
    s=normalize_sections('<p>Phụ lục II</p><p>DANH MỤC CÔNG VIỆC</p><table><tr><th>Mã</th><th>Tên nghề</th></tr>'+rows+'</table>',"doc")[0]
    s.update(document_number="01/2020/TT-BLĐTBXH",document_id="doc",review_status="reviewed",article_ids=[],artifact_ids=[],source_url="https://example.test",still_valid=True,effective_from_date=None,effective_to_date=None,version_date=None)
    chunks=make_chunks(s,lambda t:len(t.split())+2)
    assert len(chunks)>2
    for c in chunks:
        assert len(c["text"].split())+2<=1024
        assert c["locator"]["text_sha256"]==s["text_sha256"]
        assert all(any(bid in b["html"] for b in s["blocks"]) for bid in c["locator"]["block_ids"])
    assert all("Mã | Tên nghề" in c["text"] for c in chunks[1:])
    s["kind"]="unknown"
    assert not make_chunks(s,len)
    s["kind"]="form"
    assert not make_chunks(s,len)


def test_appendix_citation_checks_number_and_document():
    e=Evidence.from_payload({"chunk_id":"09-2020-tt-bldtbxh:pl2","appendix_id":"09-2020-tt-bldtbxh:pl2","appendix_number":"II","document_id":"09-2020-tt-bldtbxh","document_number":"09/2020/TT-BLĐTBXH"},"test")
    assert verify_citations("Theo Phụ lục II Thông tư 09/2020/TT-BLĐTBXH.",[e])["all_verified"]
    assert not verify_citations("Theo Phụ lục III Thông tư 09/2020/TT-BLĐTBXH.",[e])["all_verified"]
    assert not verify_citations("Theo Phụ lục II Thông tư 02/2024/TT-BLĐTBXH.",[e])["all_verified"]


@pytest.fixture
def local_catalog(tmp_path,monkeypatch):
    root=tmp_path;raw=root/"data/raw/appendix";processed=root/"data/processed/appendices_v1"
    monkeypatch.setattr(storage,"ROOT_DIR",root)
    monkeypatch.setattr(storage,"RAW_DIR",raw)
    monkeypatch.setattr(storage,"PROCESSED_DIR",processed)
    monkeypatch.setattr(storage,"INTERIM_DIR",root/"data/interim/appendix")
    artifact=storage.register_bytes(b"%PDF-1.4\nlocal test\n","doc","source.pdf","https://example.test",raw_dir=raw)
    section=normalize_sections(HTML,"doc")[1]
    section.update(document_id="doc",document_number="09/2020/TT-BLĐTBXH",article_ids=[],artifact_ids=[artifact["artifact_id"]],review_status="reviewed",download_status="downloaded",extraction_status="extracted",source_url="https://example.test",still_valid=True,version_date=None,effective_from_date=None,effective_to_date=None)
    storage.write_jsonl(processed/"appendices.jsonl",[section])
    chunks=make_chunks(section,lambda t:len(t.split())+2)
    storage.write_jsonl(processed/"chunks.jsonl",chunks)
    storage.write_json(processed/"artifacts.json",{artifact["artifact_id"]:artifact})
    return AppendixCatalog(processed),artifact,chunks


def test_local_api_preview_download_missing_file_and_path_safety(local_catalog):
    catalog,artifact,chunks=local_catalog
    with TestClient(create_app(catalog)) as client:
        listing=client.get('/api/appendices').json()
        assert listing['total']==1
        url=listing['items'][0]['view_url']
        rendered=client.get(url,params={"chunk_id":chunks[0]["chunk_id"]})
        assert rendered.status_code==200 and 'class="highlight"' in rendered.text
        assert client.get(url,params={"chunk_id":"wrong:pl3"}).status_code==404
        download=client.get('/api/files/'+artifact['artifact_id'])
        assert download.content==b"%PDF-1.4\nlocal test\n" and 'inline' in download.headers['content-disposition']
        assert 'attachment' in client.get('/api/files/'+artifact['artifact_id']+'?download=true').headers['content-disposition']
        storage.local_path(artifact['path']).unlink()
        assert client.get('/api/files/'+artifact['artifact_id']).status_code==410
        assert client.get('/api/files/unknown').status_code==404
        assert client.get('/').status_code==200
    with pytest.raises(ValueError):storage.local_path('../../.env')


def test_collector_resume_checks_hash_without_network(local_catalog):
    _,artifact,_=local_catalog
    target={"document":"09/2020/TT-BLĐTBXH","document_id":"09-2020-tt-bldtbxh","item_id":"152670"}
    old={**target,"download_status":"downloaded","files":[artifact],"metadata":{"docNum":target['document']}}
    collector=Collector()
    collector.get=lambda _:pytest.fail("valid resume must not use network")
    assert collector.one(target,old)['cache_hit']


def test_real_sample_mapping_and_forms_when_collected():
    from labor_rag.appendices.graph import jsonl
    rows=jsonl(storage.PROCESSED_DIR/'appendices.jsonl')
    if not rows:
        pytest.skip('Run collection/extraction for integration fixtures')
    tt={a['key']:a for a in rows if a['document_id']=='09-2020-tt-bldtbxh'}
    assert set(tt)=={'1','2','3','4','5'}
    assert tt['1']['kind']=='form'
    for key,article in [('2','8'),('3','9'),('4','9'),('5','10')]:
        assert tt[key]['kind']=='reference'
        assert any(l['article_number']==article for l in tt[key]['article_ids'])
    nd135={a['key']:a for a in rows if a['document_id']=='135-2020-nd-cp'}
    assert {'1','2','3'}<=set(nd135)
    tt19=[a for a in rows if a['document_id']=='19-2016-tt-bldtbxh']
    assert len(tt19)==18 and all(a['kind']=='form' for a in tt19)
    nd97={a['key']:a for a in rows if a['document_id']=='97-2022-nd-cp'}
    assert set(nd97)=={'1','2'}


def test_baseline_benchmark_refuses_rebuild_with_appendices():
    from types import SimpleNamespace
    from labor_rag.evaluation.embedding_benchmark import ensure_collection_index
    class Client:
        def get_collection(self,**kwargs):
            return SimpleNamespace(points_count=2,config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=2))))
        def scroll(self,**kwargs):return [SimpleNamespace(payload={'chunk_id':'doc:pl1','chunk_type':'appendix','text':'addon'})],None
        def delete_collection(self,**kwargs):pytest.fail('Must never delete the extended corpus')
    with pytest.raises(ValueError,match='appendices'):
        ensure_collection_index(Client(),{'collection':'legal_test_bge'},[{'chunk_id':'doc:d1','text':'base'}],None,2,rebuild=True)
