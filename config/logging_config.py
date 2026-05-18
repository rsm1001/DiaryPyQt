"""
统一日志配置模块
支持 JSON 格式输出，便于接入 ELK/Graylog 等日志分析平台
"""
import logging
import json
import socket
import sys
from logging.handlers import RotatingFileHandler


class JSONFormatter(logging.Formatter):
    """JSON 日志格式化器，输出结构化日志"""

    def __init__(self, include_hostname=True, datefmt="%Y-%m-%d %H:%M:%S"):
        super().__init__(datefmt=datefmt)
        self.include_hostname = include_hostname
        self.hostname = socket.gethostname() if include_hostname else None

    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        if self.include_hostname:
            log_obj["hostname"] = self.hostname
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            log_obj["data"] = record.extra_data
        return json.dumps(log_obj, ensure_ascii=False)


def setup_logging(
    level=logging.INFO,
    log_file=None,
    json_format=True,
    include_hostname=True,
):
    """
    统一日志配置函数

    Args:
        level: 日志级别，默认 INFO
        log_file: 日志文件路径，默认不输出到文件
        json_format: 是否使用 JSON 格式，默认 True
        include_hostname: JSON 格式是否包含主机名，默认 True
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    if json_format:
        formatter = JSONFormatter(include_hostname=include_hostname)
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_file:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)