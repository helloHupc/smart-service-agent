import logging
import os
import time
import json
import functools
from contextlib import asynccontextmanager
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

LOG_DIR = os.environ.get("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)


# ========== Server Logger: capture uvicorn HTTP/access/error logs ==========
_uvicorn_handler = TimedRotatingFileHandler(
    os.path.join(LOG_DIR, "uvicorn.log"),
    when="D", interval=1, backupCount=30, encoding="utf-8",
)
_uvicorn_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
))
for _name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
    _uv_logger = logging.getLogger(_name)
    _uv_logger.addHandler(_uvicorn_handler)
    _uv_logger.propagate = False


# ========== App Logger ==========
_app_logger = logging.getLogger("smart-service-agent")
_app_logger.propagate = False

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-5s | %(message)s"
))
_console_handler.setLevel(logging.INFO)
_app_logger.addHandler(_console_handler)

_file_handler = TimedRotatingFileHandler(
    os.path.join(LOG_DIR, "app.log"),
    when="D", interval=1, backupCount=30, encoding="utf-8",
)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"
))
_file_handler.setLevel(logging.INFO)
_app_logger.addHandler(_file_handler)

_app_logger.setLevel(logging.INFO)

logger = _app_logger


# ========== Chat Audit Logger (JSON Lines, monthly rotation) ==========
class ChatLogger:
    def __init__(self, log_dir=LOG_DIR):
        os.makedirs(log_dir, exist_ok=True)
        self._log_dir = log_dir
        self._current_month = None
        self._file = None

    def _get_path(self):
        return os.path.join(
            self._log_dir,
            f"chat-{datetime.now().strftime('%Y-%m')}.jsonl",
        )

    def _rotate_if_needed(self):
        month = datetime.now().strftime("%Y-%m")
        if month != self._current_month:
            if self._file:
                self._file.close()
            self._current_month = month
            self._file = open(self._get_path(), "a", encoding="utf-8")

    def log(self, **kwargs):
        self._rotate_if_needed()
        kwargs.setdefault("timestamp", datetime.now().isoformat())
        self._file.write(json.dumps(kwargs, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self):
        if self._file:
            self._file.close()
            self._file = None


chat_logger = ChatLogger()


# ========== Performance Monitor ==========
@asynccontextmanager
async def monitor_time(operation: str, extra: Optional[dict] = None):
    start_time = time.perf_counter()
    logger.info(f"START | {operation} | extra: {extra or {}}")
    try:
        yield
    finally:
        duration = (time.perf_counter() - start_time) * 1000
        logger.info(f"END | {operation} | duration: {duration:.2f}ms")


def monitor_time_decorator(operation: str):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            logger.info(f"START | {operation} | func: {func.__name__}")
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = (time.perf_counter() - start_time) * 1000
                logger.info(f"END | {operation} | func: {func.__name__} | duration: {duration:.2f}ms")
        return wrapper
    return decorator
