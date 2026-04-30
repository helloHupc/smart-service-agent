from typing import Dict, List, Any, Optional
import json
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.llm.openai_compatible import openai_compatible_client
from app.utils.logger import monitor_time, logger


class ReactEngine:
    """ReAct 推理引擎"""

    def __init__(self):
        self.client = openai_compatible_client
        self.max_iterations = 3  # 最小版本限制迭代次数

    async def run(
        self,
        db: AsyncSession,
        query: str,
        intent: str,
        context: Dict,
        tools: Dict,
    ) -> Dict[str, Any]:
        """执行 ReAct 循环"""
        async with monitor_time("REACT_ENGINE_RUN"):
            return await self._run(db, query, intent, context, tools)

    async def run_quick(
        self,
        db: AsyncSession,
        query: str,
        intent: str,
        context: Dict,
        tools: Dict,
        pre_search_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """快速模式：预搜索 + 单次 LLM 调用直接生成最终答案

        跳过 ReAct 的 Thought → Action → Observation 循环，
        将预搜索结果作为上下文直接发给 LLM 生成回复。
        """
        async with monitor_time("REACT_ENGINE_RUN_QUICK"):
            return await self._run_quick(db, query, intent, context, tools, pre_search_result)

    async def _run_quick(
        self,
        db: AsyncSession,
        query: str,
        intent: str,
        context: Dict,
        tools: Dict,
        pre_search_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        steps = []
        pre_products = pre_search_result.get("products", []) if pre_search_result else []

        if not self.client.has_chat_client():
            return {
                "steps": steps,
                "final_answer": None,
                "products": pre_products,
                "intent": intent
            }

        system_prompt = self._build_quick_system_prompt()
        messages = self._build_quick_messages(query, intent, context, pre_search_result)

        async with monitor_time("REACT_QUICK_LLM"):
            content = await self.client.chat_completion(
                model=settings.LLM_MODEL,
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
                system_prompt=system_prompt,
                messages=messages,
            )

        content = self._strip_react_directives(content)

        steps.append({"type": "final_answer", "content": content})

        return {
            "steps": steps,
            "final_answer": content,
            "products": self._extract_products(steps, content, pre_products),
            "intent": intent
        }

    async def _run(
        self,
        db: AsyncSession,
        query: str,
        intent: str,
        context: Dict,
        tools: Dict,
    ) -> Dict[str, Any]:
        """执行 ReAct 循环内部逻辑"""

        steps = []
        final_answer = None
        detected_intent = intent

        # 如果没有 LLM 配置，直接执行默认搜索并返回
        if not self.client.has_chat_client():
            if intent in ["product_inquiry", "price_inquiry", "spec_inquiry", "recommendation"]:
                observation = await tools["product_search"].execute(db, {"query": query})
                steps.append(
                    {
                        "type": "action",
                        "tool": "product_search",
                        "input": {"query": query},
                        "observation": observation,
                    }
                )
            return {
                "steps": steps,
                "final_answer": None,
                "products": self._extract_products(steps),
                "intent": detected_intent
            }

        system_prompt = self._build_system_prompt(tools)
        messages = self._build_messages(query, intent, context)

        for iteration in range(self.max_iterations):
            try:
                async with monitor_time(f"REACT_ITERATION_{iteration + 1}"):
                    content = await self.client.chat_completion(
                        model=settings.LLM_MODEL,
                        max_tokens=settings.LLM_MAX_TOKENS,
                        temperature=settings.LLM_TEMPERATURE,
                        system_prompt=system_prompt,
                        messages=messages,
                    )

                parsed = self._parse_response(content)

                # 尝试从响应内容中提取意图（仅在第一轮迭代且意图未定时）
                if iteration == 0:
                    # 无论 parsed 类型如何，都尝试从原始 content 中找 Intent
                    extracted_intent = self._extract_intent_from_thought(content)
                    if extracted_intent:
                        detected_intent = extracted_intent

                # 记录思考过程
                if parsed.get("thought"):
                    steps.append({"type": "thought", "content": parsed["thought"]})

                if parsed["type"] == "thought" and not parsed.get("thought"):
                    # 兼容旧逻辑
                    steps.append({"type": "thought", "content": parsed["content"]})
                    messages.append({"role": "assistant", "content": content})

                elif parsed["type"] == "action":
                    tool_name = parsed["tool"]
                    tool_input = parsed["input"]

                    if tool_name in tools:
                        observation = await tools[tool_name].execute(db, tool_input)

                        steps.append(
                            {
                                "type": "action",
                                "tool": tool_name,
                                "input": tool_input,
                                "observation": observation,
                            }
                        )

                        messages.append({"role": "assistant", "content": content})
                        messages.append(
                            {
                                "role": "user",
                                "content": f"Observation: {json.dumps(observation, ensure_ascii=False)}",
                            }
                        )
                    else:
                        break

                elif parsed["type"] == "final_answer":
                    final_answer = parsed["content"]
                    steps.append({"type": "final_answer", "content": final_answer})
                    break
                else:
                    if parsed["type"] == "thought":
                        pass
                    else:
                        final_answer = content
                        break
            except Exception as e:
                logger.warning(f"ReAct iteration failed on iteration {iteration + 1}: {e}")
                break

        return {
            "steps": steps,
            "final_answer": final_answer,
            "products": self._extract_products(steps, final_answer),
            "intent": detected_intent
        }

    def _build_system_prompt(self, tools: Dict) -> str:
        """构建系统提示"""
        tool_descriptions = "\n".join([f"- {name}: {tool.description}" for name, tool in tools.items()])

        return f"""你是保军礼品的智能客服助手。使用 ReAct 范式回答用户问题。

可用工具：
{tool_descriptions}

回答格式（严格遵循，不要使用 Markdown 加粗标记）：
Thought: [你的思考过程]
Action: [工具名称]
Action Input: [工具输入，JSON格式]

或者直接给出最终答案：
Final Answer: [你的回答]

同时，请在第一次 Thought 中识别用户意图，格式为 "Intent: [类别]"。
意图类别包括：product_inquiry, price_inquiry, spec_inquiry, recommendation, purchase_intent, complaint, greeting, other

注意：
1. 优先使用工具搜索产品信息
2. 回答要专业、友好、简洁
3. 如果用户询问价格、规格等，必须使用工具查询
4. 在 Final Answer 中提及产品时，**必须使用产品数据中提供的完整、准确的名称**，不要擅自缩写或修改，以便系统匹配产品卡片。
5. Action、Action Input、Thought、Final Answer 这些指令标签不要使用 Markdown 加粗格式（不要用 **星号** 包裹）
"""

    def _build_messages(self, query: str, intent: str, context: Dict) -> List[Dict[str, str]]:
        """构建消息列表"""
        messages: List[Dict[str, str]] = []

        history = context.get("messages", [])[-10:]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": f"用户问题: {query}"})
        return messages

    def _build_quick_system_prompt(self) -> str:
        """快速模式的系统提示：不包含工具选择，直接根据产品数据回答"""
        return """你是保军礼品的智能客服助手。根据提供的产品数据为用户生成专业、友好、简洁的回答。

要求：
1. 如果产品列表有数据，列出相关产品及其关键信息（名称、价格、特点）
2. 在回复中提及产品时，**必须使用产品数据中提供的完整、准确的名称**，不要擅自缩写或修改，以便系统匹配产品卡片。
3. 如果产品列表为空，礼貌告知用户暂未找到相关产品，并引导提供更多信息
4. 回答中提及的产品信息必须来自提供的产品数据，不要编造
5. 语气亲切、专业，像真人客服，使用"~"等语气词增强亲和力
6. 直接给出最终回复内容，禁止输出 Action、Action Input、Thought 等 ReAct 指令标签"""

    def _strip_react_directives(self, content: str) -> str:
        """去除 LLM 输出中的 ReAct 指令行（快速模式兜底）"""
        lines = content.split("\n")
        react_prefixes = ("Action:", "Action Input:", "Thought:", "Final Answer:")
        cleaned: List[str] = []
        for line in lines:
            bare = line.strip()
            while bare.startswith("**"):
                bare = bare[2:]
            while bare.startswith("__"):
                bare = bare[2:]
            if any(bare.startswith(p) for p in react_prefixes):
                continue
            cleaned.append(line)
        return "\n".join(cleaned).strip()

    def _build_quick_messages(
        self,
        query: str,
        intent: str,
        context: Dict,
        pre_search_result: Optional[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """构建快速模式消息（含预搜索结果作为上下文）"""
        messages: List[Dict[str, str]] = []

        history = context.get("messages", [])[-10:]
        for msg in history:
            clean_content = msg["content"]
            if msg["role"] == "assistant":
                clean_content = self._strip_react_directives(clean_content)
            messages.append({"role": msg["role"], "content": clean_content})

        products_text = ""
        if pre_search_result and pre_search_result.get("products"):
            products_text = "\n\n【相关产品数据】\n"
            for p in pre_search_result["products"][:20]:
                name = p.get("name", "未知")
                price = p.get("price", "暂无")
                desc = p.get("description", "")
                products_text += f"- {name}（¥{price}）：{desc}\n"

        messages.append({
            "role": "user",
            "content": f"用户问题：{query}{products_text}\n\n请根据以上产品数据回答用户问题。"
        })
        return messages

    def _extract_intent_from_thought(self, thought: str) -> Optional[str]:
        """从 Thought 文本中提取意图"""
        match = re.search(r"Intent:\s*([a-zA-Z_]+)", thought, re.IGNORECASE)
        if match:
            intent = match.group(1).lower()
            valid_intents = {
                "product_inquiry", "price_inquiry", "spec_inquiry", 
                "recommendation", "purchase_intent", "complaint", 
                "greeting", "other"
            }
            if intent in valid_intents:
                return intent
        return None

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """解析 LLM 响应（兼容 Markdown 加粗格式）"""
        content = content.strip()

        thought = None
        if self._has_prefix(content, "Thought:"):
            thought_part = self._split_after(content, "Thought:")
            if self._has_prefix(thought_part, "Action:"):
                thought = self._split_before(thought_part, "Action:").strip()
            elif self._has_prefix(thought_part, "Final Answer:"):
                thought = self._split_before(thought_part, "Final Answer:").strip()
            else:
                thought = thought_part.strip()

        if self._has_prefix(content, "Final Answer:"):
            answer = self._split_after(content, "Final Answer:").strip()
            return {
                "type": "final_answer",
                "content": answer,
                "thought": thought
            }

        if self._has_prefix(content, "Action:") and self._has_prefix(content, "Action Input:"):
            lines = content.split("\n")
            tool = None
            tool_input = None

            for line in lines:
                clean_line = line.strip()
                action_val = self._extract_md_prefix(clean_line, "Action:")
                input_val = self._extract_md_prefix(clean_line, "Action Input:")
                if action_val:
                    tool = action_val.strip()
                elif input_val:
                    try:
                        tool_input = json.loads(input_val.strip())
                    except Exception:
                        tool_input = input_val.strip()

            if tool:
                return {
                    "type": "action",
                    "tool": tool,
                    "input": tool_input,
                    "thought": thought
                }

        if thought:
            return {
                "type": "thought",
                "content": thought,
                "thought": thought
            }

        return {"type": "unknown", "content": content}

    def _extract_md_prefix(self, line: str, prefix: str) -> str:
        """从行中提取指定前缀之后的内容，兼容 **prefix** 或 **prefix:** 格式"""
        stripped = line.strip()
        bare = stripped
        while bare.startswith("**"):
            bare = bare[2:]
        while bare.startswith("__"):
            bare = bare[2:]
        if bare.startswith(prefix):
            result = bare[len(prefix):]
            while result.startswith("**"):
                result = result[2:]
            while result.endswith("**"):
                result = result[:-2]
            return result
        return ""

    def _strip_md(self, text: str) -> str:
        """去除开头 Markdown 加粗标记"""
        t = text.strip()
        while t.startswith("**"):
            t = t[2:]
        while t.startswith("__"):
            t = t[2:]
        return t

    def _has_prefix(self, text: str, prefix: str) -> bool:
        """检查文本是否包含指定前缀"""
        return prefix in text

    def _split_after(self, text: str, marker: str) -> str:
        """在 marker 之后切分文本"""
        idx = text.find(marker)
        return text[idx + len(marker):] if idx != -1 else text

    def _split_before(self, text: str, marker: str) -> str:
        """在 marker 之前切分文本"""
        idx = text.find(marker)
        return text[:idx] if idx != -1 else text

    def _extract_products(
        self,
        steps: List[Dict[str, Any]],
        final_answer: Optional[str] = None,
        pre_products: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """从步骤或预搜索结果中提取产品信息，并按 final_answer 中的出现顺序排序"""
        all_candidates = []
        if pre_products:
            all_candidates.extend(pre_products)
            
        for step in steps:
            if step["type"] == "action" and step["tool"] == "product_search":
                obs = step.get("observation", {})
                if isinstance(obs, dict) and "products" in obs:
                    all_candidates.extend(obs["products"])

        if not all_candidates:
            return []

        # 去重并保持原始顺序
        unique_candidates = {}
        ordered_pids = []
        for p in all_candidates:
            pid = p.get("product_id")
            if pid and pid not in unique_candidates:
                unique_candidates[pid] = p
                ordered_pids.append(pid)

        if not final_answer:
            return [unique_candidates[pid] for pid in ordered_pids]


        # 1. 提取在 final_answer 中明确提到的产品，并记录顺序
        found_with_pos = []
        seen_ids = set()
        
        # 预处理 final_answer，去除干扰字符
        search_text = final_answer.lower()

        for pid in ordered_pids:
            p = unique_candidates[pid]
            name = p.get("name", "").lower()
            if not name:
                continue
                
            # 尝试多种匹配方式，按优先级排序
            match_pos = -1
            
            # 方式 A: 全名匹配
            match_pos = search_text.find(name)
            
            # 方式 B: 去掉括号和规格后的核心名匹配
            if match_pos == -1:
                # 移除 (涤氨), 190克, 尺码S-4XL 等干扰项
                clean_name = re.sub(r"\(.*?\)|（.*?）|\d+克|\d+g|尺码.*|纯色|高端|翻领|圆领", "", name).strip()
                if len(clean_name) >= 2:
                    match_pos = search_text.find(clean_name)
            
            # 方式 C: 价格辅助匹配 (如果文本中出现了 "¥价格" 或 "价格元")
            if match_pos == -1 and p.get("price"):
                price_str = str(p["price"])
                if f"¥{price_str}" in search_text or f"{price_str}元" in search_text:
                    # 如果价格匹配到了，尝试在价格附近找名称关键词
                    price_pos = search_text.find(price_str)
                    # 在价格前后 50 个字符内找核心词
                    context_area = search_text[max(0, price_pos-50):min(len(search_text), price_pos+50)]
                    core_word = name[:4]
                    if core_word in context_area:
                        match_pos = price_pos # 以价格位置作为排序依据
            
            if match_pos != -1:
                found_with_pos.append((match_pos, p))
                seen_ids.add(pid)
        
        # 按在文本中出现的先后顺序排序已找到的产品
        found_with_pos.sort(key=lambda x: x[0])
        final_products = [p for _, p in found_with_pos]
        
        # 2. 将搜索结果中存在但未在文本中提及的产品追加到末尾（保持原始重排顺序）
        # 这一步非常关键：确保卡片数量不会因为 AI 没提到而减少
        unmentioned_count = 0
        for pid in ordered_pids:
            if pid not in seen_ids:
                final_products.append(unique_candidates[pid])
                seen_ids.add(pid)
                unmentioned_count += 1

        
        return final_products
