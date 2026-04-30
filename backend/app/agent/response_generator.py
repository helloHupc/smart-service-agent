from typing import Dict, Any, List

from app.config.rule_loader import rule_config


class ResponseGenerator:
    """响应生成器，优先使用 ReAct 结果，缺失时走规则兜底"""

    async def generate(
        self,
        query: str,
        intent: str,
        react_result: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        if react_result.get("final_answer"):
            return react_result["final_answer"]

        products = react_result.get("products", []) or []
        if products:
            lines: List[str] = ["为您找到以下相关产品："]
            for index, product in enumerate(products[:3], start=1):
                name = product.get("name") or "未命名产品"
                price = product.get("price")
                description = product.get("description") or "暂无描述"
                if price is not None:
                    lines.append(f"{index}. {name}（¥{price}）- {description}")
                else:
                    lines.append(f"{index}. {name} - {description}")

            if intent in {"purchase_intent", "price_inquiry", "recommendation"}:
                lines.append("如果您有预算、数量或定制要求，我可以继续帮您缩小范围。")
            return "\n".join(lines)

        templates = rule_config.templates
        if intent in templates:
            return templates[intent]

        return templates.get("default", "我已经收到您的需求。请告诉我更具体的产品关键词、预算、数量或使用场景，我会继续为您筛选合适方案。")
