from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

class MessageCreate(BaseModel):
    content: str
    session_id: Optional[UUID] = None

class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    intent: Optional[str]
    created_at: datetime
    metadata_info: Dict[str, Any] = {}

    class Config:
        from_attributes = True

class SessionCreate(BaseModel):
    user_id: Optional[int] = None

class SessionResponse(BaseModel):
    id: UUID
    user_id: Optional[int]
    started_at: datetime
    messages: List[MessageResponse] = []

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    phone: Optional[str]
    email: Optional[str]
    name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None  # 接收前端传来的 UUID 字符串

class ChatResponse(BaseModel):
    message: str
    session_id: str
    intent: Optional[str]
    should_collect_contact: bool = False
    metadata: Dict[str, Any] = {}
