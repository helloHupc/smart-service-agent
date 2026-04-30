from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import socketio

from app.config import settings
from app.api import chat, products, websocket, health
from app.models.database import init_db
from app.utils.logger import logger

# Socket.IO 服务器
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[]
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    yield

app = FastAPI(
    title="Customer Service Agent API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(products.router, prefix="/api/products", tags=["products"])

# Socket.IO 集成
socket_app = socketio.ASGIApp(sio, app)

@sio.event
async def connect(sid, environ):
    ip = environ.get("REMOTE_ADDR", "unknown")
    x_forwarded_for = environ.get("HTTP_X_FORWARDED_FOR", "")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    await sio.save_session(sid, {
        "ip": ip,
        "user_agent": environ.get("HTTP_USER_AGENT", ""),
    })
    logger.info(f"Client connected: {sid} from {ip}")

@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")

@sio.event
async def message(sid, data):
    session = await sio.get_session(sid)
    ip = session.get("ip", "unknown")
    user_agent = session.get("user_agent", "")
    await websocket.handle_message(sio, sid, data, ip=ip, user_agent=user_agent)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:socket_app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
