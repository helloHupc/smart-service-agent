from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pymilvus import MilvusClient

from app.config import settings
from app.models.database import ProductCache
from app.rag.embedder import Embedder
from app.rag.reranker import Reranker
from app.utils.logger import monitor_time

class ProductRetriever:
    """产品检索器（基于 Zilliz Cloud 向量检索 + PostgreSQL 详情获取）"""
    
    def __init__(self):
        self.embedder = Embedder()
        self.reranker = Reranker()
        self.milvus_client = MilvusClient(
            uri=settings.ZILLIZ_ENDPOINT,
            token=settings.ZILLIZ_TOKEN
        )
        
    async def search(
        self,
        db: AsyncSession,
        query: str,
        category: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict]:
        """
        搜索产品
        1. 将 query 向量化
        2. 在 Zilliz Cloud 中进行向量检索 (扩大召回范围)
        3. 根据返回的 ID 从 PostgreSQL 获取完整详情
        4. 使用 Reranker 进行业务重排
        """
        
        if not query:
            return []

        # 1. 向量化查询
        async with monitor_time("RAG_EMBED_QUERY"):
            query_vector = await self.embedder.embed_text(query)
        if not query_vector:
            return []

        # 2. 向量检索
        async with monitor_time("RAG_VECTOR_SEARCH"):
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            # 构建过滤条件（前缀匹配，支持 "广告衫" 匹配 "广告衫园领" 等）
            filter_expr = ""
            if category:
                filter_expr = f'category like "{category}%"'

            # 扩大召回范围，以便重排层有更多选择空间
            recall_limit = max(limit * 4, 20)
            
            search_results = self.milvus_client.search(
                collection_name=settings.ZILLIZ_COLLECTION_NAME,
                data=[query_vector],
                limit=recall_limit,
                filter=filter_expr,
                output_fields=["id"]
            )

        if not search_results or not search_results[0]:
            return []

        # 提取产品 ID 和 原始检索分数
        product_scores = {hit["id"]: hit["distance"] for hit in search_results[0]}
        product_ids = list(product_scores.keys())
        
        # 3. 从数据库获取详情（保持向量检索的顺序）
        async with monitor_time("RAG_DB_FETCH"):
            stmt = select(ProductCache).where(ProductCache.product_id.in_(product_ids))
            result = await db.execute(stmt)
        products_map = {p.product_id: p for p in result.scalars().all()}
        
        # 按检索顺序排列结果
        ordered_results = []
        for pid in product_ids:
            if pid in products_map:
                p = products_map[pid]
                ordered_results.append({
                    "product_id": p.product_id,
                    "name": p.name,
                    "category": p.category,
                    "description": p.description,
                    "price": float(p.price) if p.price else None,
                    "specs": p.specs,
                    "images": p.images,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                    "raw_data": p.raw_data,
                    "search_score": product_scores.get(p.product_id, 0)
                })
        
        # 4. 业务重排
        async with monitor_time("RAG_RERANK"):
            final_results = await self.reranker.rerank(query, ordered_results, top_k=limit)
            
        return final_results
