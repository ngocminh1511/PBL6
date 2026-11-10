"""Private R2 file access. Creating a client or reading config never uploads files."""
from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, urlsplit

from dotenv import load_dotenv

from labor_rag.config import ROOT_DIR
from .catalog import now, sha256


class StorageConfigurationError(ValueError):
    pass


class ObjectIntegrityError(ValueError):
    pass


def error_code(exc) -> str:
    return str(getattr(exc,"response",{}).get("Error",{}).get("Code") or type(exc).__name__)


@dataclass(frozen=True)
class StorageConfig:
    endpoint: str = field(repr=False)
    bucket: str
    access_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    region: str = "auto"
    prefix: str = "appendices_v1"

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT_DIR/".env")
        aliases={"endpoint":("OBJECT_STORAGE_ENDPOINT_URL","R2_ENDPOINT_URL"),
                 "bucket":("OBJECT_STORAGE_BUCKET","R2_BUCKET_NAME"),
                 "access_key":("OBJECT_STORAGE_ACCESS_KEY_ID","R2_ACCESS_KEY_ID"),
                 "secret_key":("OBJECT_STORAGE_SECRET_ACCESS_KEY","R2_SECRET_ACCESS_KEY")}
        values={key:next((os.environ[n].strip() for n in names if os.getenv(n,"").strip()),"") for key,names in aliases.items()}
        missing=[aliases[k][0] for k,v in values.items() if not v]
        if missing:
            raise StorageConfigurationError("Missing storage settings: "+", ".join(missing))
        provider=os.getenv("OBJECT_STORAGE_PROVIDER","s3").lower()
        if provider not in {"s3","r2"}:
            raise StorageConfigurationError("OBJECT_STORAGE_PROVIDER must be s3 or r2")
        parsed=urlsplit(values["endpoint"])
        if (parsed.scheme!="https" or not (parsed.hostname or "").endswith(".r2.cloudflarestorage.com")
                or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path.strip("/")):
            raise StorageConfigurationError("Use the HTTPS R2 S3 endpoint without a bucket path or query")
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]",values["bucket"]):
            raise StorageConfigurationError("Invalid OBJECT_STORAGE_BUCKET")
        prefix=os.getenv("OBJECT_STORAGE_PREFIX","appendices_v1").strip("/")
        if not prefix or not re.fullmatch(r"[a-zA-Z0-9_./-]+",prefix) or any(p in {".","..",""} for p in prefix.split("/")):
            raise StorageConfigurationError("Invalid OBJECT_STORAGE_PREFIX")
        return cls(**values,region=os.getenv("OBJECT_STORAGE_REGION","auto"),prefix=prefix)


def content_type(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def disposition(filename: str, *, inline: bool = False) -> str:
    filename=Path(filename.replace("\\","/")).name
    return ("inline" if inline else "attachment")+"; filename*=UTF-8''"+quote(filename,safe="")


class R2Store:
    def __init__(self, config: StorageConfig | None = None, *, client=None):
        self.config=config or StorageConfig.from_env()
        if client is None:
            import boto3
            from botocore.config import Config
            client=boto3.client("s3",endpoint_url=self.config.endpoint,region_name=self.config.region,
                aws_access_key_id=self.config.access_key,aws_secret_access_key=self.config.secret_key,
                config=Config(signature_version="s3v4",connect_timeout=10,read_timeout=60,
                              retries={"max_attempts":3,"mode":"standard"},
                              request_checksum_calculation="when_required",response_checksum_validation="when_required"))
        self.client=client

    def close(self):
        self.client.close()

    def check_bucket(self):
        self.client.head_bucket(Bucket=self.config.bucket)

    def key(self, digest: str, namespace: str):
        if not re.fullmatch(r"[0-9a-f]{64}",digest) or namespace not in {"artifacts","normalized"}:
            raise ValueError("Invalid content-addressed object identity")
        return f"{self.config.prefix}/{namespace}/{digest[:2]}/{digest}"

    def head(self, key):
        try:
            return self.client.head_object(Bucket=self.config.bucket,Key=key)
        except Exception as exc:
            if error_code(exc) in {"404","NoSuchKey","NotFound"}:
                return None
            raise

    def upload_verified(self, path: Path, digest: str, *, filename: str, namespace="artifacts") -> dict:
        """Never overwrite an existing key. Verify actual GET bytes, not ETag as a checksum."""
        payload=path.read_bytes()
        if sha256(payload)!=digest:
            raise ObjectIntegrityError("Local file hash differs from manifest")
        key=self.key(digest,namespace)
        head=self.head(key)
        uploaded=False
        if head is None:
            try:
                self.client.put_object(Bucket=self.config.bucket,Key=key,Body=payload,
                    ContentType=content_type(filename),ContentDisposition=disposition(filename),
                    Metadata={"sha256":digest},IfNoneMatch="*")
                uploaded=True
            except Exception as exc:
                if error_code(exc) not in {"412","PreconditionFailed"}:
                    raise
            head=self.head(key)
        if head is None or head.get("ContentLength")!=len(payload):
            raise ObjectIntegrityError("R2 file size differs from local file")
        if head.get("Metadata",{}).get("sha256",digest)!=digest:
            raise ObjectIntegrityError("Existing R2 key has conflicting SHA-256 metadata")
        response=self.client.get_object(Bucket=self.config.bucket,Key=key)
        body=response["Body"]
        remote_hash=hashlib.sha256()
        count=0
        try:
            while part:=body.read(1024*1024):
                remote_hash.update(part)
                count+=len(part)
        finally:
            body.close()
        if count!=len(payload) or remote_hash.hexdigest()!=digest:
            raise ObjectIntegrityError("R2 download hash differs from local file")
        return {"bucket":self.config.bucket,"key":key,"sha256":digest,"bytes":len(payload),
                "etag":head.get("ETag"),"verified_at":now(),"status":"uploaded" if uploaded else "already_present"}

    def download_url(self, artifact: dict, *, inline=False, expires=300) -> str:
        record=artifact.get("r2") or {}
        if (artifact.get("storage_backend")!="r2" or not record.get("verified_at")
                or record.get("sha256")!=artifact.get("sha256") or record.get("bucket")!=self.config.bucket
                or record.get("key")!=self.key(artifact["sha256"],"artifacts")):
            raise ObjectIntegrityError("Artifact does not have a verified R2 location in the configured bucket")
        head=self.head(record["key"])
        if head is None:
            raise FileNotFoundError("R2 object is missing")
        if head.get("ContentLength")!=artifact["bytes"] or (record.get("etag") and head.get("ETag")!=record["etag"]):
            raise ObjectIntegrityError("R2 object changed after verification")
        return self.client.generate_presigned_url("get_object",Params={"Bucket":record["bucket"],"Key":record["key"],
                "ResponseContentType":content_type(artifact["file_name"]),
                "ResponseContentDisposition":disposition(artifact["file_name"],inline=inline)},ExpiresIn=expires)
