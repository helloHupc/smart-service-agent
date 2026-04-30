import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import logging

from app.config import settings
from app.rag.retriever import ProductRetriever

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_rag_search():
    # 1. 初始化数据库连接
    engine = create_async_engine(settings.DATABASE_URL)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # 2. 初始化检索器
    retriever = ProductRetriever()
    
    # 3. 测试不同的查询
    test_queries = [
        "有没有水杯？",
        "我想买个地垫",
        "手机支架多少钱",
        "推荐一些居家用品"
    ]
    
    async with async_session_factory() as session:
        for query in test_queries:
            logger.info(f"--- 测试查询: '{query}' ---")
            try:
                results = await retriever.search(session, query, limit=3)
                if not results:
                    logger.info("未找到相关产品")
                else:
                    for i, res in enumerate(results):
                        logger.info(f"结果 {i+1}: [{res['product_id']}] {res['name']} - 价格: {res['price']} - 分类: {res['category']}")
            except Exception as e:
                logger.error(f"查询失败: {e}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_rag_search())
