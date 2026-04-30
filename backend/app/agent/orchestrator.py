from typing import Dict, Any, Optional, Callable, Awaitable
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.intent_classifier import IntentClassifier
from app.agent.react_engine import ReactEngine
from app.agent.response_generator import ResponseGenerator
from app.memory.long_term import LongTermMemory
from app.rag.retriever import ProductRetriever
from app.models.database import User
from app.tools.product_search import ProductSearchTool
from app.config import settings
from app.config.rule_loader import rule_config
from app.utils.logger import monitor_time


class AgentOrchestrator:
    """Agent 主编排器"""

    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.react_engine = ReactEngine()
        self.response_generator = ResponseGenerator()
        self.long_term_memory = LongTermMemory()
        self.retriever = ProductRetriever()
        self.tools = {
            "product_search": ProductSearchTool(self.retriever),
        }

    async def process(
        self,
        db: AsyncSession,
        message: str,
        context: Dict[str, Any],
        user_id: Optional[str] = None,  # 接收 UUID 字符串
        on_status: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        async with monitor_time("ORCHESTRATOR_PROCESS"):
            # 0. 用户识别与持久化信息加载
            db_user_id = None
            if user_id:
                # 根据 UUID 查找或同步用户信息
                stmt = select(User).where(User.uuid == user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()
                
                if user:
                    db_user_id = user.id
                    # 如果找到了老用户，同步其联系方式到当前上下文
                    if user.phone:
                        context.setdefault("collected_info", {})["phone"] = user.phone
                    if user.email:
                        context.setdefault("collected_info", {})["email"] = user.email
                else:
                    # 如果是全新的 UUID，且当前上下文有手机号（可能刚填完），则创建/关联用户
                    current_phone = context.get("collected_info", {}).get("phone")
                    if current_phone:
                        # 检查该手机号是否已存在于其他 UUID 下
                        stmt_p = select(User).where(User.phone == current_phone)
                        res_p = await db.execute(stmt_p)
                        existing_user = res_p.scalar_one_or_none()
                        
                        if existing_user:
                            # 跨设备关联：将新 UUID 绑定到老手机号用户上
                            existing_user.uuid = user_id
                            await db.commit()
                            db_user_id = existing_user.id
                        else:
                            # 完全的新用户
                            new_user = User(uuid=user_id, phone=current_phone)
                            db.add(new_user)
                            await db.commit()
                            await db.refresh(new_user)
                            db_user_id = new_user.id

            # 1. 意图识别（规则优先，LLM 识别合并至 ReAct）
            async with monitor_time("INTENT_CLASSIFICATION"):
                intent = await self.intent_classifier.classify(message, context)
            context["current_intent"] = intent

            hints = rule_config.loading_hints

            fast_track_intents = rule_config.fast_track_intents
            product_intents = rule_config.product_intents

            # 2. 长期记忆检索（并行执行）
            # 使用数据库内部的整数 ID 进行长期记忆检索
            memory_task = asyncio.create_task(
                self.long_term_memory.retrieve(db=db, user_id=db_user_id, query=message)
            )

            # ★ 快速通道：非产品类意图直接模板回复，完全跳过 LLM
            if intent in fast_track_intents:
                memories = await memory_task
                async with monitor_time("RESPONSE_GENERATION"):
                    response = await self.response_generator.generate(
                        query=message, intent=intent,
                        react_result={}, context=context,
                    )
                return {
                    "message": response,
                    "intent": intent,
                    "should_collect_contact": False,
                    "metadata": {
                        "react_steps": [],
                        "retrieved_products": [],
                        "long_term_memories": memories,
                        "user_id": user_id,
                    },
                }

            # ★ 预搜索：对产品相关意图，LLM 调用前先并行搜索
            pre_search_task = None
            if intent in product_intents:
                pre_search_task = asyncio.create_task(
                    self.tools["product_search"].execute(db, {"query": message, "limit": 5})
                )
                if on_status and hints.get("searching"):
                    await on_status(hints["searching"])

            memories = await memory_task
            context["long_term_memories"] = memories

            pre_search_result = await pre_search_task if pre_search_task else None

            # 3. ReAct 推理（产品意图走快速模式，其他走完整模式）
            if on_status and hints.get("generating"):
                await on_status(hints["generating"])

            if intent in product_intents:
                react_result = await self.react_engine.run_quick(
                    db=db, query=message, intent=intent,
                    context=context, tools=self.tools,
                    pre_search_result=pre_search_result,
                )
            else:
                react_result = await self.react_engine.run(
                    db=db, query=message, intent=intent,
                    context=context, tools=self.tools,
                )

            if react_result.get("intent"):
                intent = react_result["intent"]
                context["current_intent"] = intent

            # 4. 响应生成
            async with monitor_time("RESPONSE_GENERATION"):
                response = await self.response_generator.generate(
                    query=message,
                    intent=intent,
                    react_result=react_result,
                    context=context,
                )

        should_collect = self._should_collect_contact(context)

        if db_user_id and intent in {"purchase_intent", "recommendation", "price_inquiry"}:
            await self.long_term_memory.save(
                db=db,
                user_id=db_user_id,
                memory_type=intent,
                content=message,
            )

        return {
            "message": response,
            "intent": intent,
            "should_collect_contact": should_collect,
            "metadata": {
                "react_steps": react_result.get("steps", []),
                "retrieved_products": react_result.get("products", []),
                "long_term_memories": memories,
                "user_uuid": user_id,
            },
        }

    def _should_collect_contact(self, context: Dict[str, Any]) -> bool:
        collected = context.get("collected_info", {})
        if collected.get("phone") or collected.get("email"):
            return False

        message_count = len(context.get("messages", []))
        if message_count >= settings.CONTACT_COLLECTION_THRESHOLD * 2:
            return True

        if context.get("current_intent") in {"purchase_intent", "price_inquiry"}:
            return True

        return False
