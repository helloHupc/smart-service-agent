from typing import List

from app.llm.openai_compatible import openai_compatible_client


class Embedder:
    """基于 OpenAI-compatible 接口的向量化实现。"""

    def __init__(self):
        self.client = openai_compatible_client

    async def embed_text(self, text: str) -> List[float]:
        if not text:
            return []

        if not self.client.has_embedding_client():
            return []

        embeddings = await self.client.create_embeddings([text])
        return embeddings[0] if embeddings else []

    async def embed_text_with_info(self, text: str):
        """返回向量和限流信息"""
        if not text:
            return [], {}

        if not self.client.has_embedding_client():
            return [], {}

        embeddings, info = await self.client.create_embeddings_with_info([text])
        return (embeddings[0] if embeddings else []), info

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        if not self.client.has_embedding_client():
            return [[] for _ in texts]

        return await self.client.create_embeddings(texts)
