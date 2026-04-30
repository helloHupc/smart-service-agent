import json
from typing import Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.retriever import ProductRetriever
from app.models.database import ProductCache


class ProductSearchTool:
    """产品搜索工具"""

    def __init__(self, retriever: ProductRetriever):
        self.retriever = retriever
        self.description = "搜索保军礼品的产品信息，包括名称、价格、规格和描述。输入参数：query (搜索关键词), category (可选分类)"
        self._category_keywords: Optional[Dict[str, str]] = None

    async def _ensure_keywords(self, db: AsyncSession):
        """从数据库加载已知分类名，构建关键词映射表（惰性缓存）"""
        if self._category_keywords is not None:
            return

        result = await db.execute(
            select(ProductCache.category).where(
                ProductCache.category.isnot(None),
                ProductCache.category != "",
            ).distinct()
        )
        all_names = [row[0] for row in result.all()]

        keywords: Dict[str, str] = {}
        for name in all_names:
            clean = name.strip()
            keywords[clean] = clean
            first_word = clean.split()[0] if clean.split() else clean
            if first_word != clean:
                keywords.setdefault(first_word, first_word)
            if len(clean) >= 3:
                short = clean[:3]
                keywords.setdefault(short, short)
            elif len(clean) >= 2:
                short = clean[:2]
                keywords.setdefault(short, short)

        self._category_keywords = keywords

    async def _extract_category_from_query(self, db: AsyncSession, query: str) -> Optional[str]:
        """检查 query 是否包含已知分类关键词，返回分类名用于 LIKE 过滤"""
        if not query:
            return None
        await self._ensure_keywords(db)
        for keyword in sorted(self._category_keywords.keys(), key=len, reverse=True):
            if keyword in query:
                return self._category_keywords[keyword]
        return None

    async def execute(self, db: AsyncSession, tool_input: Any) -> Dict[str, Any]:
        """执行搜索"""
        if isinstance(tool_input, str):
            try:
                params = json.loads(tool_input)
            except Exception:
                params = {"query": tool_input}
        else:
            params = tool_input

        query = params.get("query", "")
        category = params.get("category")
        limit = params.get("limit", 5)

        if not category:
            category = await self._extract_category_from_query(db, query)
        else:
            await self._ensure_keywords(db)
            if category not in self._category_keywords:
                category = None

        products = await self.retriever.search(db, query, category, limit=limit)

        return {
            "products": products,
            "count": len(products),
        }
