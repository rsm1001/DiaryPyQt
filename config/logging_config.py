"""
统一日志配置模块
支持 JSON 格式输出，便于接入 ELK/Graylog 等日志分析平台
支持终端友好的彩色单行格式输出
"""
import logging
import json
import re
import socket
import sys
from logging.handlers import RotatingFileHandler

# Windows 10+ 启用 ANSI 转义码支持
if sys.platform == "win32":
    try:
        import os
        os.system("")
    except Exception:
        pass


class ColorFormatter(logging.Formatter):
    """终端友好的彩色单行日志格式化器"""

    RESET = "\033[0m"
    GRAY = "\033[90m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    WHITE_BOLD = "\033[97m\033[1m"

    LEVEL_COLORS = {
        "DEBUG": GRAY,
        "INFO": CYAN,
        "WARNING": YELLOW,
        "ERROR": RED,
        "CRITICAL": RED,
    }

    KV_KEY_COLOR = BLUE
    KV_VALUE_COLOR = GREEN

    def __init__(self, datefmt="%Y-%m-%d %H:%M:%S"):
        super().__init__(datefmt=datefmt)

    def format(self, record):
        parts = []

        # 1. 时间戳（灰色）：精确到毫秒
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        msecs = int(record.msecs) if isinstance(record.msecs, float) else record.msecs
        msecs_str = str(msecs).rjust(3, "0")
        parts.append(f"{self.GRAY}{timestamp}.{msecs_str}{self.RESET}")

        # 2. 级别（固定5字符，各级别固定颜色）
        level = self.format_level(record.levelname)
        parts.append(level)

        # 3. 位置（青色，固定20字符宽度）
        location = self.format_location(record)
        location = f"{location:<20}"
        parts.append(f"{self.CYAN}{location}{self.RESET}")

        # 4. 消息（白色加粗）
        message = record.getMessage()
        message = self.highlight_kv(message)
        parts.append(f"{self.WHITE_BOLD}{message}{self.RESET}")

        return " ".join(parts)

    def format_level(self, levelname):
        """级别固定5字符宽度，不足补空格"""
        color = self.LEVEL_COLORS.get(levelname, self.GRAY)
        return f"{color}{levelname:<5}{self.RESET}"

    def format_location(self, record):
        """格式化位置信息：module:line"""
        module = record.module
        if module.endswith(".py"):
            module = module[:-3]
        return f"{module}:{record.lineno}"

    def highlight_kv(self, message):
        """高亮键值对：键=值 → 键(蓝色)=值(绿色)"""

        def replacer(m):
            key = m.group(1)
            value = m.group(2)
            return f"{self.KV_KEY_COLOR}{key}{self.RESET}={self.KV_VALUE_COLOR}{value}{self.RESET}"

        pattern = r"(\w+)=(\S+)"
        return re.sub(pattern, replacer, message)


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
    json_format=False,
    color_format=True,
    include_hostname=True,
):
    """
    统一日志配置函数

    Args:
        level: 日志级别，默认 INFO
        log_file: 日志文件路径，默认不输出到文件
        json_format: 是否使用 JSON 格式，默认 False
        color_format: 是否使用彩色格式，默认 True（终端友好）
        include_hostname: JSON 格式是否包含主机名，默认 True
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    if color_format:
        formatter = ColorFormatter()
    elif json_format:
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