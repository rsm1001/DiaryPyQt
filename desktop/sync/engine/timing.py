"""跨端时间戳归一化。

桌面库写的是本机本地时间（naive），服务器写的是 UTC ISO8601。
直接比较会整体偏差一个时区（中国区 8 小时），因此所有跨端比较
必须先统一到 UTC；解析不出来时返回 None，由调用方降级为人工处理，
绝不用"当前时间"兜底。
"""
from datetime import datetime, timezone
from typing import Optional

DESKTOP_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"


def parse_desktop_time(value: Optional[str]) -> Optional[datetime]:
    """桌面 naive 时间按本机时区解释后转成 UTC。

    兼容旧库里只有日期（%Y-%m-%d）的行。
    """
    if not value:
        return None
    text = str(value).strip()
    for fmt in (DESKTOP_FORMAT, DATE_FORMAT):
        try:
            naive = datetime.strptime(text, fmt)
        except ValueError:
            continue
        # naive.astimezone() 会按系统本地时区解释，正是桌面列的语义
        return naive.astimezone(timezone.utc)
    return None


def parse_server_time(value: Optional[str]) -> Optional[datetime]:
    """服务器 UTC ISO8601（带 Z 或 offset）转 UTC；无时区按 UTC 兜底。"""
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def to_local_string(server_iso: Optional[str]) -> str:
    """服务器 UTC 时间转桌面 '%Y-%m-%d %H:%M:%S'（本机时区）。

    回写本地 updated_at 必须用它，不能用 now()，否则下一轮会把
    自己的落地误判成"本地新修改"。
    """
    parsed = parse_server_time(server_iso)
    if parsed is None:
        raise ValueError("服务器时间格式无法解析")
    return parsed.astimezone().strftime(DESKTOP_FORMAT)


def to_desktop_date(remote_date: Optional[str], server_iso: Optional[str] = None) -> str:
    """服务器只有日期，桌面列需要完整时间戳。

    保留服务器日期前缀，保证 date[:10] 与服务器一致（同步摘要取前 10 位）。
    """
    date_part = str(remote_date or "").strip()[:10]
    time_part = "00:00:00"
    parsed = parse_server_time(server_iso)
    if parsed is not None:
        time_part = parsed.astimezone().strftime("%H:%M:%S")
    return f"{date_part} {time_part}"


def pick_newer(local_value: Optional[str], remote_value: Optional[str],
               epsilon_seconds: int) -> str:
    """判断哪一侧更新，返回 'local' / 'remote' / 'tie' / 'unknown'。

    任一侧缺失或格式异常返回 'unknown'；差值在抖动阈值内返回 'tie'。
    调用方对 'tie' 与 'unknown' 一律不覆盖，转人工。
    """
    local_time = parse_desktop_time(local_value)
    remote_time = parse_server_time(remote_value)
    if local_time is None or remote_time is None:
        return "unknown"
    delta = (local_time - remote_time).total_seconds()
    if abs(delta) <= epsilon_seconds:
        return "tie"
    return "local" if delta > 0 else "remote"


def now_iso() -> str:
    """当前 UTC 时间，与服务器格式保持一致。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
