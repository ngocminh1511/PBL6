import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, DateTime, Boolean, ForeignKey, Integer, Float, JSON
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="lawyer", nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    domain = Column(String(100), default="all")  # all, lao_dong, bhxh
    retrieval_mode = Column(String(50), default="hybrid")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    
    # Explainable AI & LexRAG pipeline trace
    standalone_query = Column(Text, nullable=True)
    pipeline_trace = Column(JSON, nullable=True)
    legal_evidence = Column(JSON, nullable=True)
    citation_check = Column(JSON, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    session = relationship("ChatSession", back_populates="messages")

class DocumentRecord(Base):
    __tablename__ = "documents"
    
    id = Column(String(100), primary_key=True)  # document_id e.g. 45-2019-qh14
    title = Column(String(500), nullable=False)
    document_number = Column(String(100), nullable=True)  # e.g. 45/2019/QH14
    document_type = Column(String(50), default="pdf")      # pdf, phap_dien_html
    domain = Column(String(100), default="lao_dong")       # lao_dong, bhxh, etc.
    effective_from_date = Column(String(50), nullable=True)
    status = Column(String(50), default="completed")       # pending, processing, indexed, error
    
    chunks_count = Column(Integer, default=0)
    nodes_count = Column(Integer, default=0)
    edges_count = Column(Integer, default=0)
    ast_tree_json = Column(JSON, nullable=True)
    file_path = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class IngestionTask(Base):
    __tablename__ = "ingestion_tasks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(100), nullable=True)
    file_name = Column(String(255), nullable=False)
    document_type = Column(String(50), nullable=False)
    status = Column(String(50), default="pending")  # pending, parsing, chunking, embedding, indexing, completed, failed
    progress = Column(Float, default=0.0)           # 0.0 to 100.0
    current_step = Column(String(255), default="Bắt đầu khởi tạo...")
    total_chunks = Column(Integer, default=0)
    embedded_chunks = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SystemConfig(Base):
    __tablename__ = "system_configs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

