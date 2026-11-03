import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.backend.app.config import settings
from src.backend.app.repositories.postgres import init_db, SessionLocal
from src.backend.app.models.database import DocumentRecord, User
from src.backend.app.utils.auth import get_password_hash
from src.backend.app.routers.auth import router as auth_router
from src.backend.app.routers.chat import router as chat_router
from src.backend.app.routers.documents import router as documents_router
from src.backend.app.routers.admin import router as admin_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema
    init_db()
    
    # Seed default sample data if empty
    db = SessionLocal()
    try:
        # Default user
        if not db.query(User).filter(User.username == "admin").first():
            admin_user = User(
                username="admin",
                email="admin@lexgraph.vn",
                hashed_password=get_password_hash("admin123"),
                full_name="Quản trị viên Hệ thống",
                role="admin"
            )
            db.add(admin_user)
            db.commit()

        # Seed sample documents from UI design if DB is new
        if db.query(DocumentRecord).count() == 0:
            sample_docs = [
                DocumentRecord(
                    id="BLLD2019",
                    title="Bộ luật Lao động 2019",
                    document_number="45/2019/QH14",
                    document_type="pdf",
                    domain="lao_dong",
                    effective_from_date="2021-01-01",
                    status="completed",
                    chunks_count=412,
                    nodes_count=817,
                    edges_count=142,
                    ast_tree_json={
                        "node_id": "VN_BLLD_2019_ROOT",
                        "title": "Bộ luật Lao động 2019 (45/2019/QH14)",
                        "chapters": [
                            {"id": "Chuong_III", "title": "Chương III: Hợp đồng lao động", "sections": [
                                {"id": "Muc_3", "title": "Mục 3: Chấm dứt hợp đồng lao động", "articles": [
                                    {"id": "Dieu_35", "title": "Điều 35: Quyền đơn phương chấm dứt HĐLĐ của người lao động", "clauses": [
                                        {"id": "Khoan_1", "text": "1. Người lao động có quyền đơn phương chấm dứt hợp đồng lao động nhưng phải báo trước...", "points": [
                                            {"id": "Diem_a", "text": "a) Ít nhất 45 ngày nếu làm việc theo hợp đồng lao động không xác định thời hạn;", "chunk_id": "BLLD_D35_K1_Da"},
                                            {"id": "Diem_d", "text": "d) Đối với một số ngành, nghề, công việc đặc thù thì thời hạn báo trước thực hiện theo quy định của Chính phủ.", "chunk_id": "BLLD_D35_K1_Dd", "refers_to": "NĐ 145/2020/NĐ-CP Điều 7 Khoản 2"}
                                        ]}
                                    ]}
                                ]}
                            ]}
                        ]
                    }
                ),
                DocumentRecord(
                    id="ND145",
                    title="Nghị định 145/2020/NĐ-CP",
                    document_number="145/2020/NĐ-CP",
                    document_type="pdf",
                    domain="lao_dong",
                    effective_from_date="2021-02-01",
                    status="completed",
                    chunks_count=240,
                    nodes_count=447,
                    edges_count=84,
                    ast_tree_json={"title": "Nghị định 145/2020/NĐ-CP Hướng dẫn thi hành BLLĐ"}
                ),
                DocumentRecord(
                    id="LBHXH2014",
                    title="Luật Bảo hiểm xã hội 2014",
                    document_number="58/2014/QH13",
                    document_type="pdf",
                    domain="bhxh",
                    effective_from_date="2016-01-01",
                    status="completed",
                    chunks_count=280,
                    nodes_count=517,
                    edges_count=118,
                    ast_tree_json={"title": "Luật Bảo hiểm xã hội 2014 (58/2014/QH13)"}
                ),
                DocumentRecord(
                    id="ND115",
                    title="Nghị định 115/2015/NĐ-CP",
                    document_number="115/2015/NĐ-CP",
                    document_type="pdf",
                    domain="bhxh",
                    effective_from_date="2016-01-01",
                    status="completed",
                    chunks_count=86,
                    nodes_count=152,
                    edges_count=42,
                    ast_tree_json={"title": "Nghị định 115/2015/NĐ-CP Hướng dẫn Luật BHXH"}
                ),
                DocumentRecord(
                    id="BLDS2015",
                    title="Bộ luật Dân sự 2015",
                    document_number="91/2015/QH13",
                    document_type="pdf",
                    domain="dan_su",
                    effective_from_date="2017-01-01",
                    status="completed",
                    chunks_count=1120,
                    nodes_count=1809,
                    edges_count=310,
                    ast_tree_json={"title": "Bộ luật Dân sự 2015 (91/2015/QH13)"}
                ),
            ]
            db.add_all(sample_docs)
            db.commit()
    finally:
        db.close()

    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API cho Hệ thống Hỏi đáp & Tra cứu Luật pháp Việt Nam (Decoupled Service-Layer Architecture)",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(chat_router, prefix=settings.API_V1_PREFIX)
app.include_router(documents_router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_router, prefix=settings.API_V1_PREFIX)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.backend.app.main:app", host="0.0.0.0", port=8000, reload=True)

