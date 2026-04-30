from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.models.database import get_db
from app.models.schemas import ChatRequest, ChatResponse
from app.agent.orchestrator import AgentOrchestrator
from app.memory.short_term import ShortTermMemory
from app.tools.contact_extractor import ContactExtractor
from app.utils.privacy import mask_dict_phone

router = APIRouter()
orchestrator = AgentOrchestrator()
short_memory = ShortTermMemory()
contact_extractor = ContactExtractor()


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """REST 聊天接口"""
    session_id = request.session_id or str(uuid.uuid4())
    context = await short_memory.get_context(session_id)

    context["messages"].append({"role": "user", "content": request.message})

    contact_info = contact_extractor.extract(request.message)
    if contact_info:
        context["collected_info"].update(contact_info)

    result = await orchestrator.process(
        db=db,
        message=request.message,
        context=context,
        user_id=request.user_id,
    )

    context["messages"].append({"role": "assistant", "content": result["message"]})
    await short_memory.update_context(session_id, context)

    return ChatResponse(
        message=result["message"],
        session_id=session_id,
        intent=result.get("intent"),
        should_collect_contact=result.get("should_collect_contact", False),
        metadata={
            **result.get("metadata", {}),
            "collected_info": mask_dict_phone(context.get("collected_info", {})),
        },
    )
