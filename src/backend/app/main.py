"""The single HTTP application; imports do not open remote connections."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from labor_rag.settings import Settings


def create_app(catalog=None, *, settings=None, storage_factory=None, retrieval_factory=None):
    from labor_rag.appendices.runtime import AppendixCatalog
    from src.backend.app.repositories.postgres import Database
    from src.backend.app.services.runtime import Runtime
    from src.backend.app.routers.appendices import create_router
    from src.backend.app.routers.auth import router as auth_router
    from src.backend.app.routers.chat import router as chat_router, legacy_router
    from src.backend.app.routers.documents import router as documents_router
    from src.backend.app.routers.admin import router as admin_router
    from src.backend.app.services.ingestion import IngestionService
    config = settings or Settings()
    database = Database(config.DATABASE_URL)
    runtime = Runtime(config, database, catalog or AppendixCatalog(),
                      storage_factory=storage_factory, retrieval_factory=retrieval_factory)
    ingestion = IngestionService(runtime, database)

    @asynccontextmanager
    async def lifespan(app):
        database.start()
        try:
            try:
                runtime.load_config()
                ingestion.recover_interrupted()
            except Exception as exc:
                database.available = False
                database.error_type = type(exc).__name__
            yield
        finally:
            ingestion.close()
            runtime.close_resources()
            database.close()

    app = FastAPI(title=config.PROJECT_NAME, version=config.VERSION, lifespan=lifespan)
    app.state.database = database
    app.state.runtime = runtime
    app.state.ingestion = ingestion

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse(status_code=503, content={"detail": "Database ứng dụng chưa hoàn tất thao tác."})
    app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS,
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    for router in [create_router(runtime), auth_router, chat_router, legacy_router,
                   documents_router, admin_router]:
        app.include_router(router, prefix=config.API_V1_PREFIX)

    @app.get("/health")
    def health():
        return {"status": "alive", "service": config.PROJECT_NAME, "version": config.VERSION}

    @app.get("/", include_in_schema=False)
    def home():
        return {"service": config.PROJECT_NAME, "frontend": "http://localhost:3000",
                "api_docs": "/docs"}

    return app


app = create_app()
