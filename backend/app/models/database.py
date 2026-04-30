from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import uuid

from app.config import settings

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    uuid = Column(String(100), unique=True, index=True)
    phone = Column(String(20), unique=True)
    email = Column(String(255), unique=True)
    name = Column(String(100))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active_at = Column(TIMESTAMP)
    metadata_info = Column(JSONB, default={}) # 避免与 Base.metadata 冲突
    
    sessions = relationship("Session", back_populates="user")
    memories = relationship("UserMemory", back_populates="user")

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    started_at = Column(TIMESTAMP, default=datetime.utcnow)
    ended_at = Column(TIMESTAMP)
    metadata_info = Column(JSONB, default={})
    
    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"))
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    intent = Column(String(50))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    metadata_info = Column(JSONB, default={})
    
    session = relationship("Session", back_populates="messages")

class UserMemory(Base):
    __tablename__ = "user_memories"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    memory_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    source_message_id = Column(Integer, ForeignKey("messages.id"))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    relevance_score = Column(Float, default=1.0)
    metadata_info = Column(JSONB, default={})
    
    user = relationship("User", back_populates="memories")

class ProductCache(Base):
    __tablename__ = "products_cache"
    
    id = Column(Integer, primary_key=True)
    product_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(255))
    category = Column(String(100))
    description = Column(Text)
    price = Column(Float)
    images = Column(JSONB, default=[])
    specs = Column(JSONB, default={})
    updated_at = Column(TIMESTAMP, default=datetime.utcnow)
    raw_data = Column(JSONB, default={})

# 数据库引擎
engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with async_session() as session:
        yield session
