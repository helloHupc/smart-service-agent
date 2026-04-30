import time
import uuid
from typing import Dict

import socketio
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator import AgentOrchestrator
from app.config.rule_loader import rule_config
from app.memory.short_term import ShortTermMemory
from app.models.database import async_session
from app.tools.contact_extractor import ContactExtractor
from app.utils.logger import chat_logger, logger
from app.utils.privacy import mask_dict_phone

orchestrator = AgentOrchestrator()
short_memory = ShortTermMemory()
contact_extractor = ContactExtractor()


async def handle_message(sio: socketio.AsyncServer, sid: str, data: Dict,
                         ip: str = "unknown", user_agent: str = ""):
    start_time = time.perf_counter()
    try:
        message = data.get("message", "")
        session_id = data.get("session_id") or str(uuid.uuid4())
        user_id = data.get("user_id") # 接收前端传来的 UUID 字符串

        context = await short_memory.get_context(session_id)
        context["messages"].append({"role": "user", "content": message})

        contact_info = contact_extractor.extract(message)
        if contact_info:
            context["collected_info"].update(contact_info)
            await sio.emit("contact_collected", contact_info, room=sid)

        hints = rule_config.loading_hints

        if hints.get("analyzing"):
            await sio.emit("status", {"text": hints["analyzing"]}, room=sid)

        async def on_status(text: str):
            await sio.emit("status", {"text": text}, room=sid)

        async with async_session() as db:
            result = await orchestrator.process(
                db=db,
                message=message,
                context=context,
                user_id=user_id,
                on_status=on_status,
            )

        context["messages"].append({"role": "assistant", "content": result["message"]})
        await short_memory.update_context(session_id, context)

        await sio.emit(
            "message",
            {
                "message": result["message"],
                "session_id": session_id,
                "intent": result.get("intent"),
                "should_collect_contact": result.get("should_collect_contact", False),
                "metadata": {
                    **result.get("metadata", {}),
                    "collected_info": mask_dict_phone(context.get("collected_info", {})),
                },
            },
            room=sid,
        )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        chat_logger.log(
            ip=ip,
            session_id=session_id,
            user_id=user_id,
            question=message,
            answer=result["message"],
            intent=result.get("intent"),
            duration_ms=duration_ms,
            user_agent=user_agent,
        )
    except Exception as e:
        logger.error(f"WebSocket error for {ip}: {e}")
        await sio.emit("error", {"message": str(e)}, room=sid)
