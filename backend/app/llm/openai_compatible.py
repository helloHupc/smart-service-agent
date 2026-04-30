from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from app.config import settings
from app.utils.logger import monitor_time


class OpenAICompatibleClient:
    """统一封装 OpenAI-compatible 的对话与向量调用。"""

    def __init__(self):
        self._chat_client: Optional[AsyncOpenAI] = None
        self._embedding_client: Optional[AsyncOpenAI] = None

    def has_chat_client(self) -> bool:
        return bool(settings.LLM_API_KEY and settings.LLM_MODEL)

    def has_embedding_client(self) -> bool:
        return bool(settings.EMBEDDING_API_KEY and settings.EMBEDDING_MODEL)

    def _get_chat_client(self) -> AsyncOpenAI:
        if not self.has_chat_client():
            raise ValueError("LLM_API_KEY 或 LLM_MODEL 未配置")

        if self._chat_client is None:
            self._chat_client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL or None,
            )
        return self._chat_client

    def _get_embedding_client(self) -> AsyncOpenAI:
        if not self.has_embedding_client():
            raise ValueError("EMBEDDING_API_KEY 或 EMBEDDING_MODEL 未配置")

        if self._embedding_client is None:
            self._embedding_client = AsyncOpenAI(
                api_key=settings.EMBEDDING_API_KEY,
                base_url=settings.EMBEDDING_BASE_URL or None,
            )
        return self._embedding_client

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        client = self._get_chat_client()
        request_messages: List[Dict[str, str]] = []

        if system_prompt:
            request_messages.append({"role": "system", "content": system_prompt})

        request_messages.extend(messages)

        async with monitor_time("LLM_CHAT_COMPLETION", extra={"model": model or settings.LLM_MODEL}):
            response = await client.chat.completions.create(
                model=model or settings.LLM_MODEL,
                messages=request_messages,
                max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE if temperature is None else temperature,
            )

        content = response.choices[0].message.content
        if isinstance(content, list):
            text_parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        text_parts.append(text)
                else:
                    text = getattr(item, "text", None)
                    if text:
                        text_parts.append(text)
            return "\n".join(text_parts).strip()

        return (content or "").strip()

    async def create_embeddings(self, texts: List[str], *, model: Optional[str] = None) -> List[List[float]]:
        if not texts:
            return []

        client = self._get_embedding_client()
        # 使用 with_raw_response 获取原始响应以提取 Header
        async with monitor_time("LLM_CREATE_EMBEDDINGS", extra={"count": len(texts)}):
            response_with_raw = await client.embeddings.with_raw_response.create(
                model=model or settings.EMBEDDING_MODEL,
                input=texts,
            )
        
        # 提取限流相关的 Header
        headers = response_with_raw.headers
        ratelimit_info = {
            "limit": headers.get("modelscope-ratelimit-requests-limit"),
            "remaining": headers.get("modelscope-ratelimit-requests-remaining"),
            "model_limit": headers.get("modelscope-ratelimit-model-requests-limit"),
            "model_remaining": headers.get("modelscope-ratelimit-model-requests-remaining"),
        }
        
        # 将限流信息存入响应对象，方便上层读取（如果需要）
        response = response_with_raw.parse()
        setattr(response, "_ratelimit_info", ratelimit_info)
        
        return [item.embedding for item in response.data]

    async def create_embeddings_with_info(self, texts: List[str], *, model: Optional[str] = None):
        """返回向量以及限流信息"""
        if not texts:
            return [], {}

        client = self._get_embedding_client()
        response_with_raw = await client.embeddings.with_raw_response.create(
            model=model or settings.EMBEDDING_MODEL,
            input=texts,
        )
        
        headers = response_with_raw.headers
        ratelimit_info = {
            "limit": headers.get("modelscope-ratelimit-requests-limit"),
            "remaining": headers.get("modelscope-ratelimit-requests-remaining"),
            "model_limit": headers.get("modelscope-ratelimit-model-requests-limit"),
            "model_remaining": headers.get("modelscope-ratelimit-model-requests-remaining"),
        }
        
        response = response_with_raw.parse()
        embeddings = [item.embedding for item in response.data]
        return embeddings, ratelimit_info


openai_compatible_client = OpenAICompatibleClient()
