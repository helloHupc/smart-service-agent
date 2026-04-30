from fastapi import APIRouter
from app.models.database import engine
import redis.asyncio as redis
from app.config import settings

router = APIRouter()

@router.get("/")
async def health_check():
    """健康检查"""
    status = {
        "status": "healthy",
        "services": {
            "database": "unknown",
            "redis": "unknown"
        }
    }
    
    # 检查数据库
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        status["services"]["database"] = "ok"
    except Exception as e:
        status["services"]["database"] = f"error: {str(e)}"
        status["status"] = "unhealthy"
        
    # 检查 Redis
    try:
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        status["services"]["redis"] = "ok"
        await r.close()
    except Exception as e:
        status["services"]["redis"] = f"error: {str(e)}"
        status["status"] = "unhealthy"
        
    return status
