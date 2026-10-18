# -*- coding: utf-8 -*-
"""Google Colab GPU Embedding Script:
Chạy script này trên Google Colab với GPU T4 miễn phí để nạp vector cho cả TH1 và TH2 vào Qdrant Cloud.
Thời gian chạy: ~1-2 phút (thay vì 30-40 phút trên CPU).

Hướng dẫn:
1. Mở https://colab.research.google.com
2. Chọn Runtime -> Change runtime type -> T4 GPU
3. Chạy các lệnh:
     !pip install sentence-transformers qdrant-client
4. Upload file lao_dong_v5/chunks.jsonl và lao_dong_v6/chunks.jsonl lên Colab
5. Chạy đoạn code bên dưới!
"""

import json
import time
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, PayloadSchemaType
import uuid

# Cấu hình Qdrant Cloud của bạn
QDRANT_URL = "https://4e410f98-50c1-48fe-8cc8-f253c86c651e.sa-east-1-0.aws.cloud.qdrant.io:6333"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6YjFkMzYzZGMtY2Q1NS00OTk0LThjYmItOGUyZDU2YTllOTFkIn0.OgbSQDwB3wjnM54oAIUom9x2mAMK5FGL3TtHeVR2VkI"
MODEL_NAME = "BAAI/bge-m3"

PAYLOAD_INDEXES = {
    "document_id": PayloadSchemaType.KEYWORD,
    "mapc": PayloadSchemaType.KEYWORD,
    "meta_dieu": PayloadSchemaType.KEYWORD,
    "still_valid": PayloadSchemaType.KEYWORD,
    "effective_from_date": PayloadSchemaType.DATETIME,
}

def embed_and_upsert(chunks_file, collection_name, client, model):
    print(f"\n=======================================================")
    print(f" Bắt đầu xử lý {chunks_file} -> {collection_name}")
    print(f"=======================================================")
    
    with open(chunks_file, "r", encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f if line.strip()]
    print(f"Đã đọc {len(chunks)} chunks.")

    texts = [c["text"] for c in chunks]

    # Tính vector trên GPU (batch_size=32 trên GPU T4 rất nhanh)
    t0 = time.time()
    print("Đang tính embeddings trên GPU T4...")
    vectors = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=True)
    dim = len(vectors[0])
    print(f"Tính xong vector trong {time.time()-t0:.1f}s (Số chiều: {dim})")

    # Tạo collection nếu chưa có
    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
    )
    for field, schema in PAYLOAD_INDEXES.items():
        client.create_payload_index(collection_name, field_name=field, field_schema=schema)

    # Nạp points vào Qdrant Cloud theo batch
    print(f"Đang tải points lên Qdrant Cloud...")
    points = [
        PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, c["chunk_id"])),
            vector=v.tolist(),
            payload=c
        )
        for c, v in zip(chunks, vectors)
    ]
    
    batch_size = 128
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        client.upsert(collection_name=collection_name, points=batch)
        print(f"  Đã tải {min(i + batch_size, len(points))}/{len(points)} points...")

    print(f"HOÀN THÀNH {collection_name}!\n")

def main():
    print("Khởi tạo kết nối Qdrant Cloud và nạp Model...")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    model = SentenceTransformer(MODEL_NAME, device="cuda")

    # Nạp TH2 (lao_dong_v5)
    embed_and_upsert("chunks_v5.jsonl", "legal_ld_v5_bge", client, model)

    # Nạp TH1 (lao_dong_v6)
    embed_and_upsert("chunks_v6.jsonl", "legal_ld_v6_bge", client, model)

    print("Tất cả dữ liệu đã được nạp thành công lên Qdrant Cloud!")

if __name__ == "__main__":
    main()
