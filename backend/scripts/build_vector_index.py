import asyncio
from sqlalchemy import select

from app.models.database import ProductCache, async_session


async def build_index():
    async with async_session() as session:
        result = await session.execute(select(ProductCache))
        products = result.scalars().all()
    print(f"loaded {len(products)} products for placeholder index build")


if __name__ == "__main__":
    asyncio.run(build_index())
