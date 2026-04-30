from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.models.database import get_db, ProductCache

router = APIRouter()

@router.get("/")
async def list_products(db: AsyncSession = Depends(get_db)):
    """获取产品列表（从缓存表）"""
    result = await db.execute(select(ProductCache).limit(20))
    products = result.scalars().all()
    return products

@router.get("/{product_id}")
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    """获取单个产品详情"""
    result = await db.execute(
        select(ProductCache).where(ProductCache.product_id == product_id)
    )
    product = result.scalar_one_or_none()
    return product
