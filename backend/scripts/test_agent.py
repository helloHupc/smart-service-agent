"""产品搜索诊断脚本 - 对比有/无分类过滤的搜索差异。

用法:
    cd backend && PYTHONPATH=. python scripts/test_agent.py
"""

import asyncio
from typing import Optional

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.database import ProductCache
from app.rag.retriever import ProductRetriever
from app.tools.product_search import ProductSearchTool


def _print_sep(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# 诊断 1：直接查 PostgreSQL，确认分类数据是否入库
# ---------------------------------------------------------------------------
async def diag_pg_category(engine, session_factory):
    _print_sep("诊断 1：PostgreSQL 分类数据检查")

    async with session_factory() as db:
        total = (await db.execute(select(func.count(ProductCache.id)))).scalar()
        with_cat = (await db.execute(
            select(func.count(ProductCache.id)).where(
                ProductCache.category.isnot(None),
                ProductCache.category != "",
            )
        )).scalar()
        without_cat = (await db.execute(
            select(func.count(ProductCache.id)).where(
                (ProductCache.category.is_(None)) | (ProductCache.category == "")
            )
        )).scalar()

        print(f"产品总数: {total}")
        print(f"有分类字段的产品: {with_cat}")
        print(f"无分类字段的产品: {without_cat}")

        # 列出所有分类
        cats_result = await db.execute(
            select(ProductCache.category, func.count(ProductCache.id))
            .where(ProductCache.category.isnot(None), ProductCache.category != "")
            .group_by(ProductCache.category)
            .order_by(ProductCache.category)
        )
        cats = cats_result.all()
        print(f"\n分类分布 ({len(cats)} 种):")
        for cat, cnt in cats:
            print(f"  [{cnt:>3}件] {cat}")

        # 查"广告衫"类别的产品
        keyword = "广告衫"
        results = await db.execute(
            select(ProductCache).where(
                ProductCache.category.contains(keyword)
            ).order_by(ProductCache.name)
        )
        products = results.scalars().all()
        print(f'\n分类含"广告衫"的产品 ({len(products)} 件):')
        for p in products:
            print(f"  [{p.product_id}] {p.name} | 分类={p.category} | 价格={p.price}")

        # 如果没有广告衫分类，搜索名称为"广告"的产品
        if not products:
            results2 = await db.execute(
                select(ProductCache).where(
                    ProductCache.name.contains("广告")
                ).order_by(ProductCache.name)
            )
            name_products = results2.scalars().all()
            print(f'\n名称含"广告"的产品 ({len(name_products)} 件):')
            for p in name_products:
                print(f"  [{p.product_id}] {p.name} | 分类={p.category} | 价格={p.price}")


# ---------------------------------------------------------------------------
# 诊断 2：向量搜索（不带分类过滤）
# ---------------------------------------------------------------------------
async def diag_search_no_category(db: AsyncSession, retriever: ProductRetriever, query: str, limit: int = 10):
    _print_sep(f"诊断 2：向量搜索（无分类过滤）- query='{query}'")

    results = await retriever.search(db, query, category=None, limit=limit)
    print(f"返回 {len(results)} 条结果:\n")
    for i, r in enumerate(results):
        print(f"  {i+1}. [{r['product_id']}] {r['name']}")
        print(f"     分类={r['category']} | 价格={r['price']}")
        desc = (r.get("description") or "")[:80]
        if desc:
            print(f"     描述={desc}")
    if not results:
        print("  ⚠️ 无结果")
    return results


# ---------------------------------------------------------------------------
# 诊断 3：向量搜索（带分类过滤）
# ---------------------------------------------------------------------------
async def diag_search_with_category(db: AsyncSession, retriever: ProductRetriever, query: str, category: str, limit: int = 10):
    _print_sep(f"诊断 3：向量搜索（category='{category}'）- query='{query}'")

    results = await retriever.search(db, query, category=category, limit=limit)
    print(f"返回 {len(results)} 条结果:\n")
    for i, r in enumerate(results):
        print(f"  {i+1}. [{r['product_id']}] {r['name']}")
        print(f"     分类={r['category']} | 价格={r['price']}")
    if not results:
        print("  ⚠️ 无结果")
    return results


# ---------------------------------------------------------------------------
# 诊断 4：ProductSearchTool 端到端对比
# ---------------------------------------------------------------------------
async def diag_tool_compare(db: AsyncSession, tool: ProductSearchTool, retriever: ProductRetriever):
    _print_sep("诊断 4：ProductSearchTool 端到端对比")

    # ★ 测试前缀匹配：直接用 retriever 传 category="广告衫"
    print("\n--- Zilliz 前缀匹配验证 (retriever.search category='广告衫') ---")
    r0 = await retriever.search(db, "广告衫", category="广告衫", limit=20)
    print(f"category='广告衫' (LIKE 前缀匹配): 返回 {len(r0)} 条")
    for p in r0:
        print(f"  [{p['product_id']}] {p['name']} | 分类={p['category']} | 价格={p['price']}")

    # ★ 测试自动提取：tool.execute 不传 category
    print("\n--- 自动提取分类 (tool.execute 不传 category) ---")
    r1 = await tool.execute(db, {"query": "广告衫有哪些"})
    print(f"自动提取: 返回 {r1['count']} 条")
    for p in r1["products"]:
        print(f"  [{p['product_id']}] {p['name']} | 分类={p['category']} | 价格={p['price']}")

    # ★ 测试显式传 category
    r2 = await tool.execute(db, {"query": "广告衫", "category": "广告衫"})
    print(f"\n显式 category='广告衫': 返回 {r2['count']} 条")
    for p in r2["products"]:
        print(f"  [{p['product_id']}] {p['name']} | 分类={p['category']} | 价格={p['price']}")

    # 对比统计
    ids_prefix = {p["product_id"] for p in r0}
    ids_auto = {p["product_id"] for p in r1["products"]}
    ids_manual = {p["product_id"] for p in r2["products"]}

    print(f"\n对比:")
    print(f"  LIKE前缀匹配命中: {len(ids_prefix)} 条")
    print(f"  自动提取命中:      {len(ids_auto)} 条")
    print(f"  显式category命中:  {len(ids_manual)} 条")
    print(f"  三者交集: {len(ids_prefix & ids_auto & ids_manual)} 条")

    # 验证：显示 PG 中所有广告衫产品的数量
    from app.models.database import ProductCache
    from sqlalchemy import select
    pg_result = await db.execute(
        select(ProductCache).where(ProductCache.category.contains("广告衫"))
    )
    pg_all = pg_result.scalars().all()
    print(f"\n  PG 广告衫产品总数: {len(pg_all)} 条")
    if ids_prefix:
        coverage = len(ids_prefix) / len(pg_all) * 100 if pg_all else 0
        print(f"  LIKE前缀匹配覆盖率: {coverage:.0f}%")


# ---------------------------------------------------------------------------
# 诊断 0：打印原始 API 数据结构，定位分类字段
# ---------------------------------------------------------------------------
async def diag_raw_api_fields(session_factory):
    _print_sep("诊断 0：检查 API 原始数据结构（定位分类字段名）")

    async with session_factory() as db:
        # 取前3条产品的 raw_data
        result = await db.execute(select(ProductCache).limit(3))
        products = result.scalars().all()

        if not products:
            print("  ⚠️ 数据库中没有产品")
            return

        for p in products:
            print(f"\n--- 产品 {p.product_id}: {p.name} ---")
            raw = p.raw_data or {}
            if raw:
                # 列出所有原始字段的键
                print(f"  API 字段: {list(raw.keys())}")
                # 打印可能的分类相关字段
                for key in raw:
                    if any(kw in key.lower() for kw in ["cat", "分类", "type", "sort", "kind", "cate"]):
                        val = raw[key]
                        if isinstance(val, str) and len(val) > 100:
                            val = val[:100] + "..."
                        print(f"    → {key} = {val}")
            else:
                print("  raw_data 为空")


# ---------------------------------------------------------------------------
# 辅助：获取真实分类名
# ---------------------------------------------------------------------------
async def get_real_category(db: AsyncSession, keyword: str) -> Optional[str]:
    """从 PostgreSQL 查找含 keyword 的分类名"""
    result = await db.execute(
        select(ProductCache.category).where(
            ProductCache.category.contains(keyword)
        ).limit(1)
    )
    row = result.scalar()
    return row if row else None


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------
async def main():
    print("=" * 60)
    print("  产品搜索诊断 - 对比有/无分类过滤的搜索差异")
    print("=" * 60)
    print(f"DB: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
    print(f"Zilliz: {settings.ZILLIZ_COLLECTION_NAME} @ {settings.ZILLIZ_ENDPOINT}")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        # 诊断 0：检查 API 原始数据字段名
        await diag_raw_api_fields(session_factory)

        # 诊断 1：检查 PostgreSQL 分类数据
        await diag_pg_category(engine, session_factory)

        retriever = ProductRetriever()
        tool = ProductSearchTool(retriever)

        async with session_factory() as db:
            # 诊断 2：无分类过滤搜索
            await diag_search_no_category(db, retriever, "广告衫有哪些", limit=10)

        async with session_factory() as db:
            # 找真实的分类名
            real_cat = await get_real_category(db, "广告衫")
            if real_cat:
                print(f"\n>>> 找到真分类名: '{real_cat}'")

            # 诊断 3：带分类过滤搜索（用真实分类名 + 前缀）
            search_cat = "广告衫"
            await diag_search_with_category(db, retriever, "广告衫", category=search_cat, limit=20)

        async with session_factory() as db:
            # 诊断 4：工具端到端对比
            await diag_tool_compare(db, tool, retriever)

    finally:
        await engine.dispose()

    print("\n" + "=" * 60)
    print("  诊断完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
