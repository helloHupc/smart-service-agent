from typing import List, Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import UserMemory


class LongTermMemory:
    """长期记忆管理，基于 PostgreSQL 的 `user_memories` 表。"""

    async def retrieve(
        self,
        db: AsyncSession,
        user_id: Optional[int],
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        if not user_id:
            return []

        result = await db.execute(
            select(UserMemory)
            .where(UserMemory.user_id == user_id)
            .order_by(UserMemory.relevance_score.desc(), UserMemory.created_at.desc())
            .limit(limit)
        )
        memories = result.scalars().all()
        return [
            {
                "id": memory.id,
                "memory_type": memory.memory_type,
                "content": memory.content,
                "relevance_score": memory.relevance_score,
                "created_at": memory.created_at.isoformat() if memory.created_at else None,
            }
            for memory in memories
        ]

    async def save(
        self,
        db: AsyncSession,
        user_id: Optional[int],
        memory_type: str,
        content: str,
        source_message_id: Optional[int] = None,
        relevance_score: float = 1.0,
    ) -> Optional[UserMemory]:
        if not user_id or not content:
            return None

        memory = UserMemory(
            user_id=user_id,
            memory_type=memory_type,
            content=content,
            source_message_id=source_message_id,
            relevance_score=relevance_score,
        )
        db.add(memory)
        await db.commit()
        await db.refresh(memory)
        return memory
