from typing import Dict, Any, Optional
import json
import redis.asyncio as redis
from app.config import settings
from app.utils.logger import logger

class ShortTermMemory:
    """短期记忆（会话上下文）管理"""
    
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self.redis_prefix = settings.REDIS_PREFIX
        self.ttl = 7200  # 2小时
        self._redis_client = None
        self._local_storage = {} # 兜底内存存储

    def _get_key(self, key: str) -> str:
        """获取带前缀的 Redis Key"""
        return f"{self.redis_prefix}{key}"

    async def _get_redis(self):
        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(self.redis_url, decode_responses=True)
                # 测试连接
                await self._redis_client.ping()
            except Exception as e:
                logger.warning(f"Failed to connect to Redis at {self.redis_url}, falling back to local storage: {e}")
                self._redis_client = False # 标记为不可用
        return self._redis_client

    async def get_context(self, session_id: str) -> Dict[str, Any]:
        """获取会话上下文"""
        if not session_id:
            return self._get_empty_context()
            
        client = await self._get_redis()
        if client:
            try:
                context_json = await client.get(self._get_key(f"session:{session_id}:context"))
                if context_json:
                    return json.loads(context_json)
            except Exception as e:
                logger.error(f"Redis get_context error: {e}")
        else:
            context_json = self._local_storage.get(self._get_key(f"session:{session_id}:context"))
            if context_json:
                return json.loads(context_json)
            
        return self._get_empty_context()
        
    async def update_context(self, session_id: str, context: Dict[str, Any]):
        """更新会话上下文"""
        if not session_id:
            return
            
        client = await self._get_redis()
        context_json = json.dumps(context)
        
        if client:
            try:
                await client.set(self._get_key(f"session:{session_id}:context"), context_json, ex=self.ttl)
            except Exception as e:
                logger.error(f"Redis update_context error: {e}")
        else:
            self._local_storage[self._get_key(f"session:{session_id}:context")] = context_json
        
    def _get_empty_context(self) -> Dict[str, Any]:
        return {
            "messages": [],
            "current_intent": None,
            "collected_info": {},
            "last_activity": None
        }
