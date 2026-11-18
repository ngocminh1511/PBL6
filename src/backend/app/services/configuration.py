"""Configuration contracts, secret storage and isolated, read-only diagnostics."""
from contextlib import closing
from datetime import datetime, timezone
from importlib.util import find_spec
from time import perf_counter
from urllib.parse import urlsplit, urlunsplit
from labor_rag.llm_providers import CLOUD_API_PROVIDERS, base_url_field, model_field, secret_field

GROUP_FIELDS = {
    "llm": {"llm_provider", "llm_reasoning", "gemini_model", "gemini_api_key", "openai_model", "openai_api_key",
            "anthropic_model", "anthropic_api_key", "local_llm_base_url", "local_llm_model", "local_llm_api_key"},
    "embedding": {"embedding_model", "embedding_backend", "query_embedding_backend", "modal_app_name", "hf_token"},
    "qdrant": {"qdrant_url", "qdrant_api_key", "qdrant_collection", "qdrant_timeout", "collection_models"},
    "neo4j": {"neo4j_uri", "neo4j_user", "neo4j_password", "neo4j_database"},
    "r2": {"object_storage_provider", "object_storage_endpoint_url", "object_storage_region", "object_storage_bucket",
           "object_storage_prefix", "object_storage_access_key_id", "object_storage_secret_access_key"},
    "redis": {"redis_enabled", "redis_url", "embedding_cache_ttl", "session_cache_ttl"},
    "ocr": {"ocr_model", "ocr_device", "ocr_dpi", "ocr_beamsearch", "ocr_semantic_chunking", "ocr_semantic_model", "max_upload_bytes"},
}
for provider in CLOUD_API_PROVIDERS:
    GROUP_FIELDS["llm"].update({model_field(provider), secret_field(provider), base_url_field(provider)})
EDITABLE = set().union(*GROUP_FIELDS.values())
SECRETS = {"gemini_api_key", "openai_api_key", "anthropic_api_key", "local_llm_api_key", "hf_token",
           "qdrant_api_key", "neo4j_password", "object_storage_access_key_id", "object_storage_secret_access_key", "redis_url"}
SECRETS.update(secret_field(provider) for provider in CLOUD_API_PROVIDERS)


class DiagnosticFailure(ValueError):
    def __init__(self, code, message):
        self.code, self.safe_message = code, message
        super().__init__(message)


def cipher(key):
    from cryptography.fernet import Fernet
    if not key:
        raise ValueError("Cần CONFIG_ENCRYPTION_KEY để lưu thông tin xác thực.")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError):
        raise ValueError("CONFIG_ENCRYPTION_KEY chưa đúng định dạng Fernet.") from None


def encode_overrides(values, key):
    public, encrypted = {}, {}
    for name, value in values.items():
        if name in SECRETS and value:
            encrypted[name] = cipher(key).encrypt(value.encode()).decode()
        else:
            public[name] = value
    return public, encrypted


def decode_overrides(record, key):
    values = {k: v for k, v in record.get("overrides", {}).items() if k in EDITABLE}
    encrypted = record.get("encrypted_secrets", {})
    if encrypted:
        try:
            decoder = cipher(key)
            values.update({k: decoder.decrypt(v.encode()).decode() for k, v in encrypted.items() if k in SECRETS})
        except Exception:
            raise ValueError("Không giải mã được cấu hình đã lưu; kiểm tra CONFIG_ENCRYPTION_KEY.") from None
    return values


def public_url(value):
    try:
        url = urlsplit(value)
        if not url.hostname:
            return ""
        host = f"[{url.hostname}]" if ":" in url.hostname else url.hostname
        if url.port:
            host += f":{url.port}"
        return urlunsplit((url.scheme, host, url.path, "", ""))
    except ValueError:
        return ""


def validate_urls(config, fields=EDITABLE):
    for field, value, schemes in [
        ("qdrant_url", config.QDRANT_URL, {"http", "https"}),
        ("neo4j_uri", config.NEO4J_URI, {"bolt", "bolt+s", "bolt+ssc", "neo4j", "neo4j+s", "neo4j+ssc"}),
        ("local_llm_base_url", config.LOCAL_LLM_BASE_URL, {"http", "https"}),
        *((base_url_field(provider), getattr(config, base_url_field(provider).upper()), {"https"})
          for provider in CLOUD_API_PROVIDERS),
        ("object_storage_endpoint_url", config.OBJECT_STORAGE_ENDPOINT_URL, {"https"}),
    ]:
        if field not in fields or not value:
            continue
        url = urlsplit(value)
        if url.scheme not in schemes or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("URL chưa hợp lệ; nhập thông tin xác thực vào ô riêng.")
        _ = url.port
    if "redis_url" in fields and config.REDIS_URL:
        url = urlsplit(config.REDIS_URL)
        if url.scheme not in {"redis", "rediss"} or not url.hostname:
            raise ValueError("Redis URL phải dùng redis:// hoặc rediss://.")
        _ = url.port


def failure_message(exc):
    """Never include exception text: SDK errors may echo keys, URLs or payloads."""
    if isinstance(exc, DiagnosticFailure):
        return exc.code, exc.safe_message
    from labor_rag.generation.llm_client import EmptyCompletion
    if isinstance(exc, EmptyCompletion):
        if exc.truncated:
            return "output_limit", "Model dùng hết giới hạn token đầu ra trước khi trả lời; giảm mức suy luận hoặc chọn model khác."
        return "empty_response", "Model không trả về nội dung văn bản; kiểm tra model và mức suy luận."
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = response.get("ResponseMetadata", {}).get("HTTPStatusCode") or code
    name = type(exc).__name__.lower()
    # Python import/file failures also contain "notfound" in their type names.
    # Classify them before remote 404-style errors.
    if isinstance(exc, ImportError):
        return "dependency", "Thiếu thư viện cần thiết trong môi trường backend."
    if isinstance(exc, FileNotFoundError):
        return "model_missing", "Chưa có đủ file model trên máy backend; chuẩn bị model rồi kiểm tra lại."
    if code in {401, 403} or "auth" in name or "forbidden" in name:
        return "authentication", "Thông tin xác thực không hợp lệ hoặc chưa đủ quyền."
    if code == 429 or "ratelimit" in name or "resourceexhausted" in name:
        return "quota", "Đã đạt hạn mức dịch vụ; kiểm tra quota và thử lại sau."
    if code == 413:
        return "request_too_large", "Nội dung yêu cầu vượt giới hạn dịch vụ; giảm dữ liệu gửi hoặc chọn hạn mức phù hợp."
    if code == 404 or "notfound" in name or "databasenotfound" in name:
        return "not_found", "Không tìm thấy model, collection, database hoặc bucket đã chọn."
    if isinstance(exc, TimeoutError) or "timeout" in name:
        return "timeout", "Dịch vụ không phản hồi trong thời gian cho phép."
    if isinstance(code, int) and 500 <= code < 600:
        return "provider_error", "Nhà cung cấp đang quá tải hoặc gặp lỗi tạm thời; thử lại sau."
    return "unavailable", "Dịch vụ chưa hoàn tất thao tác; kiểm tra địa chỉ, cấu hình và trạng thái dịch vụ."


def check_service(service, config):
    started = perf_counter()
    result = {"service": service, "status": "passed", "message": "Kiểm tra thành công.", "details": {}}
    llm_required = [model_field(config.LLM_PROVIDER).upper()]
    if config.LLM_PROVIDER != "local":
        llm_required.append(secret_field(config.LLM_PROVIDER).upper())
    endpoint_field = base_url_field(config.LLM_PROVIDER)
    if endpoint_field:
        llm_required.append(endpoint_field.upper())
    required = {
        "llm": llm_required,
        "embedding": ["EMBEDDING_MODEL"], "qdrant": ["QDRANT_URL", "QDRANT_COLLECTION"],
        "neo4j": ["NEO4J_URI", "NEO4J_USER", "NEO4J_DATABASE"],
        "r2": ["OBJECT_STORAGE_ENDPOINT_URL", "OBJECT_STORAGE_BUCKET", "OBJECT_STORAGE_ACCESS_KEY_ID", "OBJECT_STORAGE_SECRET_ACCESS_KEY"],
        "redis": ["REDIS_URL"] if config.REDIS_ENABLED else [], "ocr": [],
    }
    missing = [key.lower() for key in required[service] if not getattr(config, key)]
    try:
        if missing:
            result.update(status="not_configured", message="Chưa điền đủ thông tin.", details={"missing_fields": missing})
        else:
            validate_urls(config, GROUP_FIELDS[service])
            result["details"] = _check(service, config)
            if service == "redis" and not config.REDIS_ENABLED:
                result.update(status="disabled", message="Redis đang tắt.")
    except Exception as exc:
        error, message = failure_message(exc)
        result.update(status="failed", message=message, details={"error": error})
    result.update(checked_at=datetime.now(timezone.utc).isoformat(), latency_ms=round((perf_counter() - started) * 1000))
    return result


def _check(service, config):
    if service == "llm":
        from labor_rag.generation.llm_client import LLMClient
        with closing(LLMClient(config)) as client:
            client.complete("Connection test. Reply with OK only.", "OK", max_tokens=64, reasoning="off")
        return {"provider": config.LLM_PROVIDER, "model": client.model}
    if service == "embedding":
        from labor_rag.services.embedding import EmbeddingProvider
        vectors = {}
        for backend in dict.fromkeys([config.EMBEDDING_BACKEND, config.query_backend]):
            with closing(EmbeddingProvider(config, backend=backend)) as provider:
                vector = provider.encode("Kiểm tra kết nối embedding")
                if len(vector) == 0:
                    raise ValueError("Empty embedding")
                vectors[backend] = len(vector)
        if len(set(vectors.values())) != 1:
            raise DiagnosticFailure("dimensions", "Hai nguồn embedding trả về số chiều khác nhau; kiểm tra model trên local và Modal.")
        return {"dimensions": next(iter(vectors.values())), "backends": vectors}
    if service == "qdrant":
        from qdrant_client import QdrantClient
        with closing(QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY or None, timeout=10)) as client:
            info = client.get_collection(config.QDRANT_COLLECTION)
            dimension = getattr(info.config.params.vectors, "size", None)
            if dimension is None:
                raise ValueError("Unsupported vector layout")
            return {"dimensions": dimension, "points": info.points_count}
    if service == "neo4j":
        from labor_rag.services.neo4j import create_neo4j_driver
        with create_neo4j_driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
                                  connection_timeout=10, max_transaction_retry_time=0) as driver:
            driver.verify_connectivity()
            with driver.session(database=config.NEO4J_DATABASE) as session:
                from neo4j import Query
                row = session.run(Query("RETURN 1 AS ready", timeout=10)).single()
                if row["ready"] != 1:
                    raise ValueError("Neo4j not ready")
        return {"database": config.NEO4J_DATABASE}
    if service == "r2":
        from labor_rag.appendices.object_storage import R2Store, StorageConfig
        with closing(R2Store(StorageConfig.from_settings(config), timeout=10, retries=0)) as store:
            store.check_bucket()
        return {"bucket": config.OBJECT_STORAGE_BUCKET}
    if service == "redis":
        if not config.REDIS_ENABLED:
            return {}
        from redis import Redis
        with closing(Redis.from_url(config.REDIS_URL, socket_connect_timeout=10, socket_timeout=10)) as client:
            if not client.ping():
                raise ValueError("Redis ping failed")
        return {}
    return check_ocr(config)


def check_ocr(config):
    from pathlib import Path
    import yaml
    from labor_rag.config import VIETOCR_DIR
    for dependency in ("vietocr", "cv2", "torch", "pymupdf"):
        if find_spec(dependency) is None:
            raise ModuleNotFoundError(dependency)
    import torch
    device = config.OCR_DEVICE or ("cuda:0" if torch.cuda.is_available() else "cpu")
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise DiagnosticFailure("device", "GPU CUDA chưa khả dụng trên máy backend; chọn CPU/Auto hoặc kiểm tra driver.")
    model_file = {"vgg_transformer": "vgg-transformer.yml", "vgg_seq2seq": "vgg-seq2seq.yml"}[config.OCR_MODEL]
    merged = {}
    for name in ("base.yml", model_file):
        path = VIETOCR_DIR / name
        if not path.is_file():
            raise FileNotFoundError(name)
        merged.update(yaml.safe_load(path.read_text(encoding="utf-8")))
    if not (VIETOCR_DIR / Path(merged["weights"]).name).is_file():
        raise FileNotFoundError("OCR weights")
    if config.OCR_SEMANTIC_CHUNKING:
        from sentence_transformers import SentenceTransformer
        SentenceTransformer(config.OCR_SEMANTIC_MODEL, token=config.HF_TOKEN or None, local_files_only=True)
    return {"model": config.OCR_MODEL, "device": device, "dpi": config.OCR_DPI}
