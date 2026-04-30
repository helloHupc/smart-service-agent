from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    """
    项目配置类。
    使用 pydantic-settings，会自动从环境变量或 .env 文件中读取配置。
    如果环境变量中存在同名配置，则会覆盖此处的默认值。
    """
    
    # 数据库配置
    DATABASE_URL: str = "postgresql+asyncpg://xxx:xxx@localhost:5432/xxx"
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PREFIX: str = "smart-service-agent:"
    
    # Zilliz Cloud 配置
    ZILLIZ_ENDPOINT: str = "https://xxx.cloud.zilliz.com.cn"
    ZILLIZ_TOKEN: str = "xxx"
    ZILLIZ_COLLECTION_NAME: str = "xxx"
    
    # OpenAI-compatible 对话模型配置
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = "ark-code-latest"
    LLM_MAX_TOKENS: int = 2000
    LLM_TEMPERATURE: float = 0.2

    # OpenAI-compatible 向量模型配置
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-4B"
    EMBEDDING_DIM: int = 2560
    
    # 业务配置
    MAX_CONTEXT_MESSAGES: int = 10
    CONTACT_COLLECTION_THRESHOLD: int = 3  # 对话N轮后引导留联系方式
    
    # 日志配置
    LOG_DIR: str = "logs"

    # 产品 API 配置
    PRODUCT_API_KEY: str = ""
    
    class Config:
        # 指定读取 .env 文件
        env_file = ".env"
        # 如果 .env 文件不存在，也不报错
        env_file_encoding = 'utf-8'
        extra = "ignore"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
