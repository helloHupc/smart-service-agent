from typing import Dict, List

from app.config import settings
from app.config.rule_loader import rule_config
from app.llm.openai_compatible import openai_compatible_client


class IntentClassifier:
    """意图分类器"""

    INTENTS = [
        "product_inquiry",      # 产品咨询
        "price_inquiry",        # 价格询问
        "spec_inquiry",         # 规格询问
        "recommendation",       # 推荐请求
        "purchase_intent",      # 购买意向
        "complaint",            # 投诉
        "greeting",             # 问候
        "thanks",               # 感谢
        "farewell",             # 道别
        "capability",           # 能力询问
        "other"                 # 其他
    ]

    def __init__(self):
        self.client = openai_compatible_client

    async def classify(self, message: str, context: Dict) -> str:
        """分类用户意图（规则优先，从 YAML 配置加载）"""

        message_lower = message.lower()
        intent_rules = rule_config.intent_rules

        for intent_name, keywords in intent_rules.items():
            if any(isinstance(word, str) and word in message_lower for word in keywords):
                return intent_name

        if not self.client.has_chat_client():
            return "product_inquiry"

        return "other"
