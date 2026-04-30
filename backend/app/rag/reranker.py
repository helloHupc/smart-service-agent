from typing import List, Dict, Any
import json
from datetime import datetime


class Reranker:
    """
    产品重排器：基于业务规则和语义相关性进行综合排序。
    
    排序维度：
    1. 是否上架 (is_online) - 硬性过滤/极低权重
    2. 是否热门 (is_hot) - 加分
    3. 信息完整度 (images, description) - 加分
    4. 时效性 (updated_at) - 加分
    5. 语义相关性 (similarity) - 基础分
    """

    async def rerank(self, query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        if not candidates:
            return []

        # 1. 识别用户意图
        query_lower = query.lower()
        is_latest_intent = any(k in query_lower for k in ["最新", "刚上架", "新品", "新出的"])
        is_hot_intent = any(k in query_lower for k in ["热门", "火爆", "推荐", "最火"])
        is_cheap_intent = any(k in query_lower for k in ["便宜", "低价", "最低价", "划算", "性价比"])
        # 识别“最”字开头的强价格意图
        is_strong_cheap_intent = any(k in query_lower for k in ["最便宜", "最低价", "价格最低"])
        is_expensive_intent = any(k in query_lower for k in ["贵", "高价", "高端", "高档", "奢华"])
        is_strong_expensive_intent = any(k in query_lower for k in ["最贵", "最高价", "价格最高"])

        scored_results = []
        now = datetime.utcnow().timestamp()

        for item in candidates:
            # 解析原始数据
            raw = item.get("raw_data") or {}
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except:
                    raw = {}

            # --- 基础过滤 ---
            # 如果明确标记为下架，给予极大的负分（不直接过滤是为了保证在结果极少时仍有返回，但排在最后）
            is_online = raw.get("is_online", 1)
            online_score = 0 if str(is_online) == "1" else -100

            # --- 业务加分 ---
            # 1. 热门商品
            is_hot = str(raw.get("is_hot", 0)) == "1"
            hot_weight = 10.0 if is_hot_intent else 5.0
            hot_score = hot_weight if is_hot else 0

            # 2. 信息完整度
            has_img = 1 if item.get("images") else 0
            has_desc = 1 if item.get("description") else 0
            quality_score = (has_img * 3.0) + (has_desc * 2.0)

            # 3. 时效性 (updated_at)
            # 尝试从 raw_data 获取，如果没有则用 item 里的，再没有则用当前时间
            updated_at_str = raw.get("updated_at") or item.get("updated_at")
            recency_score = 0
            if updated_at_str:
                try:
                    if isinstance(updated_at_str, datetime):
                        dt = updated_at_str
                    else:
                        # 尝试解析常见的 ISO 格式 (如 2024-01-01T00:00:00 或 2024-01-01 00:00:00)
                        iso_str = str(updated_at_str).replace('Z', '+00:00').replace(' ', 'T')
                        dt = datetime.fromisoformat(iso_str)
                    
                    # 计算距离现在的天数，越近分数越高（30天内线性衰减）
                    days_diff = (now - dt.timestamp()) / (24 * 3600)
                    recency_weight = 10.0 if is_latest_intent else 5.0
                    recency_score = max(0, recency_weight * (1 - days_diff / 30))
                except:
                    pass

            # 4. 语义相关性 (假设输入中带有 score)
            # 向量检索的 score 通常在 0-1 之间（COSINE）
            similarity_score = item.get("search_score", 0.5) * 2.0

            # 5. 价格得分
            price_score = 0
            price = item.get("price")
            if price is not None and price > 0:
                if is_cheap_intent:
                    # 基础价格分：价格越低分越高
                    # 使用 100/price 可以在低价区间产生较大差异
                    base_price_score = 100.0 / (price + 1.0)
                    
                    # 如果是“最便宜”这种强意图，给予极高的权重，确保其主导地位
                    if is_strong_cheap_intent:
                        price_score = base_price_score * 10.0
                    else:
                        price_score = base_price_score * 2.0
                elif is_expensive_intent:
                    # 基础价格分：价格越高分越高
                    base_price_score = price / 10.0
                    
                    # 如果是“最贵”这种强意图，给予极高的权重
                    if is_strong_expensive_intent:
                        price_score = base_price_score * 10.0
                    else:
                        price_score = base_price_score * 2.0

            # --- 综合得分 ---
            total_score = online_score + hot_score + quality_score + recency_score + similarity_score + price_score
            
            item["rerank_score"] = total_score
            scored_results.append(item)

        # 按得分降序排列
        scored_results.sort(key=lambda x: x["rerank_score"], reverse=True)

        # 返回前 top_k 个
        return scored_results[:top_k]
