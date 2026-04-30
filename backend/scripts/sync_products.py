import asyncio
import httpx
from sqlalchemy import select
from pymilvus import MilvusClient, DataType
import logging

from app.config import settings
from app.models.database import ProductCache, async_session
from app.rag.embedder import Embedder

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fetch_all_products():
    """分页抓取所有产品数据"""
    all_products = []
    page = 1
    page_size = 20  # 调大一点提高效率
    
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            url = f"https://api.smart-service.cn/v1/web/gifts?page={page}&page_size={page_size}"
            logger.info(f"正在抓取第 {page} 页数据: {url}")
            
            headers = {}
            if settings.PRODUCT_API_KEY and settings.PRODUCT_API_KEY != "your_api_key":
                headers["Authorization"] = f"Bearer {settings.PRODUCT_API_KEY}"
            
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                # 根据 API 结构解析数据
                # 结构: {"code": 0, "msg": "success", "data": {"list": [...], "page": 1, "page_size": 20, "total": 26}}
                data_content = result.get("data", {})
                if isinstance(data_content, list):
                    products = data_content
                    total = len(products)
                    current_page = page
                    page_size_val = page_size
                else:
                    products = data_content.get("list", [])
                    total = data_content.get("total", 0)
                    current_page = data_content.get("page", page)
                    page_size_val = data_content.get("page_size", page_size)
                
                if not products:
                    break
                
                all_products.extend(products)
                logger.info(f"第 {page} 页抓取完成，获取到 {len(products)} 个产品 (总计: {total})")
                
                # 计算总页数
                import math
                last_page = math.ceil(total / page_size_val) if page_size_val > 0 else 1
                
                if current_page >= last_page:
                    break
                    
                page += 1
            except Exception as e:
                logger.error(f"抓取第 {page} 页失败: {e}")
                break
                
    return all_products


async def fetch_categories() -> dict:
    """从 API 获取 category_id → category_name 映射"""
    url = "https://api.smart-service.cn/v1/web/categories"
    logger.info(f"正在获取分类列表: {url}")

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()
        result = response.json()

    categories = result.get("data", [])
    cat_map = {}
    for cat in categories:
        cat_id = cat.get("id")
        cat_name = cat.get("name", "")
        if cat_id and cat_name:
            cat_map[cat_id] = cat_name
    logger.info(f"获取到 {len(cat_map)} 个分类: {list(cat_map.values())}")
    return cat_map


def init_zilliz_collection(client: MilvusClient):
    """初始化 Zilliz 集合"""
    collection_name = settings.ZILLIZ_COLLECTION_NAME
    
    if client.has_collection(collection_name):
        logger.info(f"集合 {collection_name} 已存在")
        # 如果需要重新初始化，可以取消下面注释
        # client.drop_collection(collection_name)
    
    if not client.has_collection(collection_name):
        logger.info(f"创建集合 {collection_name}")
        client.create_collection(
            collection_name=collection_name,
            dimension=settings.EMBEDDING_DIM,
            primary_field_name="id",
            id_type="string",
            max_length=100,
            auto_id=False,
            enable_dynamic_field=True
        )

async def sync_to_storage(products, category_map: dict = None):
    """同步到数据库和 Zilliz Cloud"""
    if not products:
        logger.warning("没有产品数据需要同步")
        return

    if category_map is None:
        category_map = {}

    embedder = Embedder()
    zilliz_client = MilvusClient(
        uri=settings.ZILLIZ_ENDPOINT,
        token=settings.ZILLIZ_TOKEN
    )
    
    init_zilliz_collection(zilliz_client)
    
    async with async_session() as session:
        for product in products:
            if not isinstance(product, dict):
                logger.warning(f"跳过非字典格式的产品数据: {product}")
                continue
                
            product_id = str(product.get("id") or "")
            if not product_id:
                continue

            name = product.get("name", "")
            description = product.get("description", "")
            cat_id = product.get("category_id")
            category = category_map.get(cat_id, "") if cat_id else ""
            if not category:
                category = product.get("category_name") or product.get("category", "")
            price = product.get("price")
            specs = product.get("specs", {})
            
            # 处理图片：API 返回 main_pic 对象和 detail_pic 列表
            main_pic = product.get("main_pic", {})
            main_url = main_pic.get("full_url") if isinstance(main_pic, dict) else None
            
            detail_pics = product.get("detail_pic", [])
            detail_urls = [p.get("full_url") for p in detail_pics if isinstance(p, dict)]
            
            images = []
            if main_url:
                images.append(main_url)
            images.extend(detail_urls)

            # 1. 同步到 PostgreSQL
            result = await session.execute(
                select(ProductCache).where(ProductCache.product_id == product_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.name = name
                existing.category = category
                existing.description = description
                existing.price = price
                existing.images = images
                existing.specs = specs
                existing.raw_data = product
            else:
                session.add(
                    ProductCache(
                        product_id=product_id,
                        name=name,
                        category=category,
                        description=description,
                        price=price,
                        images=images,
                        specs=specs,
                        raw_data=product,
                    )
                )

            # 2. 准备向量化文本
            # 组合：名称 + 分类 + 描述 + 规格
            specs_str = "; ".join([f"{k}: {v}" for k, v in specs.items()]) if isinstance(specs, dict) else ""
            text_to_embed = f"""产品名称: {name}
分类: {category}
描述: {description}
规格: {specs_str}"""
            
            # 3. 向量化并同步到 Zilliz
            try:
                if not text_to_embed.strip():
                    logger.warning(f"产品 {product_id} ({name}) 文本内容为空，跳过向量化")
                    continue

                # 增加重试逻辑和频率限制，避免 ModelScope 429 错误
                vector = None
                max_retries = 3
                ratelimit_info = {}
                for attempt in range(max_retries):
                    try:
                        vector, ratelimit_info = await embedder.embed_text_with_info(text_to_embed)
                        if vector:
                            break
                    except Exception as e:
                        if "429" in str(e) and attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 2
                            logger.warning(f"触发频率限制 (429)，等待 {wait_time} 秒后重试...")
                            await asyncio.sleep(wait_time)
                        else:
                            raise e

                if vector:
                    zilliz_client.upsert(
                        collection_name=settings.ZILLIZ_COLLECTION_NAME,
                        data=[{
                            "id": product_id,
                            "vector": vector,
                            "name": name,
                            "category": category,
                            "price": float(price) if price else 0.0
                        }]
                    )
                    
                    # 打印限流信息
                    rem = ratelimit_info.get("model_remaining", "unknown")
                    limit = ratelimit_info.get("model_limit", "unknown")
                    logger.info(f"产品 {product_id} ({name}) 同步成功 | 模型额度剩余: {rem}/{limit}")
                    
                    # 每次成功后稍微停顿，保护 API
                    await asyncio.sleep(0.5)
                else:
                    logger.warning(f"产品 {product_id} ({name}) 向量化返回为空")
            except Exception as e:
                logger.error(f"产品 {product_id} 向量化或同步 Zilliz 失败: {e}")

        await session.commit()

async def main():
    logger.info("开始同步产品数据...")
    cat_map = await fetch_categories()
    products = await fetch_all_products()
    logger.info(f"共获取到 {len(products)} 个产品")
    
    await sync_to_storage(products, cat_map)
    logger.info("同步任务完成")

if __name__ == "__main__":
    asyncio.run(main())
