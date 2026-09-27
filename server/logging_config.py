"""请求追踪和结构化日志。"""
from contextvars import ContextVar
import logging
from typing import Any, Dict, Tuple


_request_id: ContextVar[str] = ContextVar("diary_request_id", default="-")


class RequestIdFilter(logging.Filter):
    """为没有显式 request_id 的日志补充当前请求 ID。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = _request_id.get()
        return True


class StructuredLogger(logging.LoggerAdapter):
    """保留结构化 extra 字段并自动加入 request_id。"""

    def process(self, message: Any, kwargs: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        extra = dict(kwargs.get("extra") or {})
        extra.setdefault("request_id", _request_id.get())
        kwargs["extra"] = extra
        return message, kwargs


def configure_logging() -> None:
    """初始化日记后端日志格式。"""
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s request_id=%(request_id)s %(name)s %(message)s"
    ))
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def get_logger(name: str) -> StructuredLogger:
    """获取带 request_id 的日志适配器。"""
    return StructuredLogger(logging.getLogger(name), {})


def set_request_id(request_id: str):
    """设置当前请求 ID。"""
    return _request_id.set(request_id)


def reset_request_id(token: Any) -> None:
    """恢复请求前的 request ID。"""
    _request_id.reset(token)


def current_request_id() -> str:
    """获取当前请求 ID。"""
    return _request_id.get()
