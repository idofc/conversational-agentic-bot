from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker as async_sessionmaker
from sqlalchemy.dialects.postgresql import JSON
from pgvector.sqlalchemy import Vector
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL connection URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/conversational_bot"
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

class UseCaseDB(Base):
    __tablename__ = "use_cases"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)
    uri_context = Column(String(255), unique=True, index=True)
    title = Column(String(255))
    description = Column(Text)
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to documents
    documents = relationship("DocumentDB", back_populates="use_case", cascade="all, delete-orphan")

class DocumentDB(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    use_case_id = Column(Integer, ForeignKey("use_cases.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default="processing")
    
    # Relationship
    use_case = relationship("UseCaseDB", back_populates="documents")
    chunks = relationship("DocumentChunkDB", back_populates="document", cascade="all, delete-orphan")

class DocumentChunkDB(Base):
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))  # OpenAI text-embedding-3-small dimension
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    document = relationship("DocumentDB", back_populates="chunks")

class ConversationDB(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    use_case_id = Column(Integer, ForeignKey("use_cases.id"), nullable=False)
    title = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    use_case = relationship("UseCaseDB")
    messages = relationship("MessageDB", back_populates="conversation", cascade="all, delete-orphan")

class MessageDB(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    msg_metadata = Column("metadata", JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    conversation = relationship("ConversationDB", back_populates="messages")

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
