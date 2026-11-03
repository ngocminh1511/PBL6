"""R2 promotion requires verified GET bytes; tests use a private in-memory S3 fake."""
import io
from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from labor_rag.appendices import catalog as local
from labor_rag.appendices.object_storage import ObjectIntegrityError, R2Store, StorageConfig
from labor_rag.appendices.sync_r2 import run
from labor_rag.appendices.runtime import AppendixCatalog
from labor_rag.app.api import create_app


class S3:
    def __init__(self):
        self.objects={}
        self.puts=0
        self.corrupt=False
    def head_bucket(self,**kwargs):return {}
    def head_object(self,Bucket,Key):
        if Key not in self.objects:
            raise ClientError({'Error':{'Code':'404'}},'HeadObject')
        o=self.objects[Key]
        return {'ContentLength':len(o['Body']),'Metadata':o['Metadata'],'ETag':'verified-etag'}
    def put_object(self,**kwargs):
        assert kwargs['IfNoneMatch']=='*'
        if kwargs['Key'] in self.objects:
            raise ClientError({'Error':{'Code':'PreconditionFailed'}},'PutObject')
        self.objects[kwargs['Key']]=kwargs
        self.puts+=1
    def get_object(self,Bucket,Key):
        data=self.objects[Key]['Body']
        return {'Body':io.BytesIO(b'x'*len(data) if self.corrupt else data)}
    def generate_presigned_url(self,operation,Params,ExpiresIn):
        self.signed=Params
        assert operation=='get_object' and ExpiresIn<=300
        return 'https://download.example/verified-object'
    def close(self):pass


def store(s3):
    return R2Store(StorageConfig(endpoint='https://example.r2.cloudflarestorage.com',bucket='test-bucket',access_key='test-key',secret_key='test-secret'),client=s3)


@pytest.fixture
def files(tmp_path,monkeypatch):
    raw=tmp_path/'data/raw/appendix';out=tmp_path/'data/processed/appendices_v1'
    monkeypatch.setattr(local,'ROOT_DIR',tmp_path)
    monkeypatch.setattr(local,'RAW_DIR',raw)
    monkeypatch.setattr(local,'PROCESSED_DIR',out)
    monkeypatch.setattr(local,'INTERIM_DIR',tmp_path/'data/interim/appendix')
    a=local.register_bytes(b'%PDF-1.4\nsource\n','doc','nguon.pdf','https://example.test',raw_dir=raw)
    local.write_json(raw/'manifest.json',{'storage_backend':'local','documents':{'doc':{'files':[dict(a)]}},'artifacts':{a['artifact_id']:dict(a)}})
    local.write_json(out/'artifacts.json',{a['artifact_id']:dict(a)})
    local.write_json(out/'manifest.json',{'storage_backend':'local'})
    normalized=out/'normalized';normalized.mkdir()
    (normalized/'doc_pl1.html').write_text('<p>Phụ lục I</p>',encoding='utf8')
    return raw,out,a


def test_hash_verified_upload_is_immutable_and_resumable(files):
    _,_,a=files
    s3=S3();r2=store(s3)
    path=local.local_path(a['path'])
    first=r2.upload_verified(path,a['sha256'],filename=a['file_name'])
    second=r2.upload_verified(path,a['sha256'],filename=a['file_name'])
    assert first['status']=='uploaded' and second['status']=='already_present'
    assert s3.puts==1 and first['key']==second['key']
    s3.corrupt=True
    with pytest.raises(ObjectIntegrityError,match='download hash'):
        r2.upload_verified(path,a['sha256'],filename=a['file_name'])


def test_conflicting_existing_key_is_never_overwritten(files):
    _,_,a=files
    s3=S3();r2=store(s3);key=r2.key(a['sha256'],'artifacts')
    s3.objects[key]={'Body':b'wrong data','Metadata':{'sha256':'0'*64}}
    with pytest.raises(ObjectIntegrityError):
        r2.upload_verified(local.local_path(a['path']),a['sha256'],filename=a['file_name'])
    assert s3.puts==0 and s3.objects[key]['Body']==b'wrong data'


def test_check_never_uploads_and_sync_keeps_ids_and_local_copies(files):
    raw,out,a=files
    s3=S3()
    result=run(upload=False,store=store(s3),raw_dir=raw,output_dir=out,progress=None)
    assert result['status']=='checked' and s3.puts==0
    result=run(upload=True,store=store(s3),raw_dir=raw,output_dir=out,progress=None)
    assert result['status']=='synced' and result['verified_file_locations']==2
    manifest=local.load_manifest(raw)
    current=manifest['artifacts'][a['artifact_id']]
    assert current['path']==a['path'] and current['sha256']==a['sha256']
    assert manifest['storage_backend']=='r2' and local.valid_artifact(current)
    assert local.read_json(raw/'manifest.before_r2.json')['storage_backend']=='local'
    assert local.read_json(out/'artifacts.json')[a['artifact_id']]['r2']==current['r2']
    again=run(upload=True,store=store(s3),raw_dir=raw,output_dir=out,progress=None)
    assert again['uploaded_this_run']==0 and again['reused_this_run']==2 and s3.puts==2


def test_bad_remote_bytes_are_not_promoted(files):
    raw,out,a=files
    s3=S3();s3.corrupt=True
    result=run(upload=True,store=store(s3),raw_dir=raw,output_dir=out,progress=None)
    assert result['status']=='partial' and result['errors']
    assert local.load_manifest(raw)['artifacts'][a['artifact_id']].get('storage_backend')=='local'


def test_api_redirects_verified_r2_and_falls_back_to_local(files):
    raw,out,a=files
    s3=S3()
    run(upload=True,store=store(s3),raw_dir=raw,output_dir=out,progress=None)
    catalog=AppendixCatalog(out)
    with TestClient(create_app(catalog,storage_factory=lambda:store(s3))) as client:
        url='/api/files/'+a['artifact_id']
        response=client.get(url,follow_redirects=False)
        assert response.status_code==307 and response.headers['x-storage-backend']=='r2'
        assert s3.signed['ResponseContentDisposition'].startswith('inline')
        client.get(url+'?download=true',follow_redirects=False)
        assert s3.signed['ResponseContentDisposition'].startswith('attachment')
        record=local.read_json(out/'artifacts.json')[a['artifact_id']]['r2']
        s3.objects.pop(record['key'])
        fallback=client.get(url)
        assert fallback.status_code==200 and fallback.content==local.local_path(a['path']).read_bytes()
        assert fallback.headers['x-storage-backend']=='local-fallback'
        local.local_path(a['path']).unlink()
        assert client.get(url).status_code==410


def test_storage_config_accepts_existing_object_storage_names(tmp_path,monkeypatch):
    from labor_rag.appendices import object_storage
    monkeypatch.setattr(object_storage,'ROOT_DIR',tmp_path)
    values={'OBJECT_STORAGE_PROVIDER':'s3','OBJECT_STORAGE_ENDPOINT_URL':'https://example.r2.cloudflarestorage.com',
            'OBJECT_STORAGE_BUCKET':'test-bucket','OBJECT_STORAGE_ACCESS_KEY_ID':'test-key','OBJECT_STORAGE_SECRET_ACCESS_KEY':'test-secret'}
    for key,value in values.items():monkeypatch.setenv(key,value)
    config=StorageConfig.from_env()
    assert config.bucket=='test-bucket' and 'test-secret' not in repr(config) and 'test-key' not in repr(config)
