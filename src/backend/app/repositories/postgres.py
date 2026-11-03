from typing import Optional, List, Tuple
from datetime import datetime
from sqlalchemy import create_engine, desc, func, or_
from sqlalchemy.orm import sessionmaker, Session
from src.backend.app.config import settings
from src.backend.app.models.database import Base, User, ChatSession, ChatMessage, DocumentRecord, IngestionTask, SystemConfig
from src.backend.app.utils.pagination import encode_cursor, decode_cursor

# Setup Engine & Session Maker with fallback for sqlite if needed
db_url = settings.DATABASE_URL
engine = None

if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
    try:
        import psycopg2
        test_engine = create_engine(db_url, pool_pre_ping=True)
        # Test real connection immediately
        with test_engine.connect() as conn:
            pass
        engine = test_engine
        print("[PostgresRepository] Connected successfully to PostgreSQL.")
    except Exception as e:
        print(f"[PostgresRepository] Notice: PostgreSQL connection failed ({e}). Automatically using SQLite fallback for local running.")
        sqlite_path = settings.INTERIM_DIR / "lexgraph.db"
        engine = create_engine(f"sqlite:///{sqlite_path}", connect_args={"check_same_thread": False})
else:
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ================= USER REPOSITORY =================
class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

# ================= SESSION & MESSAGE REPOSITORY =================
class ChatRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_session(self, user_id: str, title: str, domain: str = "all", retrieval_mode: str = "hybrid") -> ChatSession:
        session = ChatSession(
            user_id=user_id,
            title=title,
            domain=domain,
            retrieval_mode=retrieval_mode
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: str, user_id: Optional[str] = None) -> Optional[ChatSession]:
        query = self.db.query(ChatSession).filter(ChatSession.id == session_id)
        if user_id:
            query = query.filter(ChatSession.user_id == user_id)
        return query.first()

    def list_sessions_cursor(
        self, user_id: str, cursor: Optional[str] = None, limit: int = 15
    ) -> Tuple[List[ChatSession], Optional[str], bool, int]:
        total_count = self.db.query(func.count(ChatSession.id)).filter(ChatSession.user_id == user_id).scalar() or 0
        query = self.db.query(ChatSession).filter(ChatSession.user_id == user_id)
        
        decoded = decode_cursor(cursor)
        if decoded:
            cursor_time_str, cursor_id = decoded
            cursor_time = datetime.fromisoformat(cursor_time_str)
            query = query.filter(
                or_(
                    ChatSession.updated_at < cursor_time,
                    (ChatSession.updated_at == cursor_time) & (ChatSession.id < cursor_id)
                )
            )
            
        items = query.order_by(desc(ChatSession.updated_at), desc(ChatSession.id)).limit(limit + 1).all()
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]
            last_item = items[-1]
            next_cursor = encode_cursor(last_item.updated_at, last_item.id)
        else:
            next_cursor = None
            
        return items, next_cursor, has_more, total_count

    def add_message(
        self, 
        session_id: str, 
        role: str, 
        content: str,
        standalone_query: Optional[str] = None,
        pipeline_trace: Optional[dict] = None,
        legal_evidence: Optional[list] = None,
        citation_check: Optional[dict] = None,
        execution_time_ms: Optional[int] = None
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            standalone_query=standalone_query,
            pipeline_trace=pipeline_trace,
            legal_evidence=legal_evidence,
            citation_check=citation_check,
            execution_time_ms=execution_time_ms
        )
        self.db.add(msg)
        
        # Update session updated_at
        session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.updated_at = datetime.utcnow()
            
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_messages(self, session_id: str) -> List[ChatMessage]:
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

# ================= DOCUMENT REPOSITORY =================
class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, document_id: str) -> Optional[DocumentRecord]:
        return self.db.query(DocumentRecord).filter(DocumentRecord.id == document_id).first()

    def list_documents_cursor(
        self, 
        domain: Optional[str] = None, 
        search: Optional[str] = None, 
        cursor: Optional[str] = None, 
        limit: int = 10
    ) -> Tuple[List[DocumentRecord], Optional[str], bool, int]:
        query = self.db.query(DocumentRecord)
        
        if domain and domain != "all":
            query = query.filter(DocumentRecord.domain == domain)
            
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    DocumentRecord.title.ilike(search_pattern),
                    DocumentRecord.document_number.ilike(search_pattern),
                    DocumentRecord.id.ilike(search_pattern)
                )
            )
            
        total_count = query.count()
        
        decoded = decode_cursor(cursor)
        if decoded:
            cursor_time_str, cursor_id = decoded
            cursor_time = datetime.fromisoformat(cursor_time_str)
            query = query.filter(
                or_(
                    DocumentRecord.created_at < cursor_time,
                    (DocumentRecord.created_at == cursor_time) & (DocumentRecord.id < cursor_id)
                )
            )
            
        items = query.order_by(desc(DocumentRecord.created_at), desc(DocumentRecord.id)).limit(limit + 1).all()
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]
            last_item = items[-1]
            next_cursor = encode_cursor(last_item.created_at, last_item.id)
        else:
            next_cursor = None
            
        return items, next_cursor, has_more, total_count

    def save(self, doc: DocumentRecord) -> DocumentRecord:
        existing = self.get_by_id(doc.id)
        if existing:
            for k, v in vars(doc).items():
                if not k.startswith("_"):
                    setattr(existing, k, v)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            self.db.add(doc)
            self.db.commit()
            self.db.refresh(doc)
            return doc

# ================= INGESTION TASK REPOSITORY =================
class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, task: IngestionTask) -> IngestionTask:
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_by_id(self, task_id: str) -> Optional[IngestionTask]:
        return self.db.query(IngestionTask).filter(IngestionTask.id == task_id).first()

    def update_progress(
        self, 
        task_id: str, 
        progress: float, 
        step: str, 
        status: Optional[str] = None, 
        embedded_chunks: int = 0,
        total_chunks: int = 0,
        error_message: Optional[str] = None
    ) -> Optional[IngestionTask]:
        task = self.get_by_id(task_id)
        if not task:
            return None
        task.progress = progress
        task.current_step = step
        if status:
            task.status = status
        if embedded_chunks:
            task.embedded_chunks = embedded_chunks
        if total_chunks:
            task.total_chunks = total_chunks
        if error_message:
            task.error_message = error_message
        self.db.commit()
        self.db.refresh(task)
        return task
