"""将已映射日记的服务器查看累计安全合并至桌面数据库。"""
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

logger = logging.getLogger(__name__)


class ViewSyncConflict(RuntimeError):
    """统计源或本地检查点不可靠，拒绝写入。"""


def _local_time(value: str, require_zone: bool = False) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ViewSyncConflict("最后查看时间无效，停止合并") from exc
    if require_zone and parsed.tzinfo is None:
        raise ViewSyncConflict("服务器查看时间缺少时区")
    return parsed.astimezone().replace(tzinfo=None) if parsed.tzinfo else parsed


def enqueue_local_view(cursor: sqlite3.Cursor, local_id: int) -> None:
    """映射已经完成时才在原查看事务内保存待同步事件。"""
    table = cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = ? AND name = ?",
        ("table", "desktop_view_sync_state"),
    ).fetchone()
    if table is None:
        return
    mapped = cursor.execute(
        "SELECT 1 FROM desktop_view_sync_state WHERE local_id = ?", (local_id,)
    ).fetchone()
    if mapped is None:
        return
    cursor.execute(
        "INSERT INTO desktop_view_outbox (event_id, local_id, viewed_at) VALUES (?, ?, ?)",
        (str(uuid4()), local_id, datetime.now().astimezone().isoformat()),
    )


class LocalViewRepository:
    """服务器累计检查点与桌面查看次数在同一 SQLite 事务提交。"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        if not self.db_path.is_file():
            raise ViewSyncConflict("本地日记数据库不存在")

    def has_checkpoint(self) -> bool:
        """仅在人工首次合并之后启动自动检查。"""
        with sqlite3.connect(str(self.db_path)) as connection:
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = ? AND name = ?",
                ("table", "desktop_view_sync_state"),
            ).fetchone()
            if table is None:
                return False
            return connection.execute("SELECT 1 FROM desktop_view_sync_state LIMIT 1").fetchone() is not None

    def prepare_baselines(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """先冻结电脑历史基线，以后的查看才能进入待同步队列。"""
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS desktop_view_sync_state (
                    local_id INTEGER PRIMARY KEY, remote_id TEXT NOT NULL UNIQUE,
                    remote_count INTEGER NOT NULL CHECK(remote_count >= 0))"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS desktop_view_baseline (
                    local_id INTEGER PRIMARY KEY, remote_id TEXT NOT NULL UNIQUE,
                    source_id TEXT NOT NULL UNIQUE, view_count INTEGER NOT NULL,
                    last_viewed_at TEXT)"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS desktop_view_outbox (
                    event_id TEXT PRIMARY KEY, local_id INTEGER NOT NULL, viewed_at TEXT NOT NULL)"""
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS desktop_view_baseline_ack (source_id TEXT PRIMARY KEY)"
            )
            prepared = []
            for item in rows:
                local_id, remote_id = item["local_id"], item["remote_id"]
                if not isinstance(local_id, int) or not isinstance(remote_id, str) or not remote_id:
                    raise ViewSyncConflict("初始映射无效")
                local = connection.execute(
                    "SELECT date, view_count, last_viewed_at FROM diaries WHERE id = ?", (local_id,)
                ).fetchone()
                if local is None or str(local["date"])[:10] != item["date"]:
                    raise ViewSyncConflict("本地日记缺失或日期变化")
                baseline = connection.execute(
                    "SELECT remote_id, source_id, view_count, last_viewed_at "
                    "FROM desktop_view_baseline WHERE local_id = ?", (local_id,)
                ).fetchone()
                checkpoint = connection.execute(
                    "SELECT remote_id FROM desktop_view_sync_state WHERE local_id = ?", (local_id,)
                ).fetchone()
                if checkpoint and (checkpoint["remote_id"] != remote_id or not baseline):
                    raise ViewSyncConflict("已有不可验证的查看检查点，禁止重复导入")
                if baseline:
                    if baseline["remote_id"] != remote_id:
                        raise ViewSyncConflict("初始映射已变更")
                    acknowledged = connection.execute(
                        "SELECT 1 FROM desktop_view_baseline_ack WHERE source_id = ?",
                        (baseline["source_id"],),
                    ).fetchone()
                    if acknowledged is None:
                        prepared.append(dict(baseline))
                    continue
                count, viewed_at = local["view_count"], local["last_viewed_at"]
                if (not isinstance(count, int) or count < 0
                        or (count > 0 and not viewed_at) or (count == 0 and viewed_at)):
                    raise ViewSyncConflict("电脑历史查看次数与时间不一致")
                timestamp = (_local_time(viewed_at).astimezone().isoformat()
                             if viewed_at else None)
                source_id = "desktop-initial:" + remote_id
                connection.execute(
                    "INSERT INTO desktop_view_sync_state (local_id, remote_id, remote_count) "
                    "VALUES (?, ?, ?)", (local_id, remote_id, count),
                )
                connection.execute(
                    "INSERT INTO desktop_view_baseline "
                    "(local_id, remote_id, source_id, view_count, last_viewed_at) "
                    "VALUES (?, ?, ?, ?, ?)", (local_id, remote_id, source_id, count, timestamp),
                )
                prepared.append({"remote_id": remote_id, "source_id": source_id,
                                 "view_count": count, "last_viewed_at": timestamp})
            connection.commit()
            return prepared
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def acknowledge_baseline(self, source_id: str) -> None:
        """标记历史基线已上传，避免每次后台同步重复导入。"""
        with sqlite3.connect(str(self.db_path)) as connection:
            frozen = connection.execute(
                "SELECT 1 FROM desktop_view_baseline WHERE source_id = ?", (source_id,)
            ).fetchone()
            if frozen is None:
                raise ViewSyncConflict("历史基线未冻结，拒绝标记为已上传")
            connection.execute(
                "INSERT OR IGNORE INTO desktop_view_baseline_ack (source_id) VALUES (?)",
                (source_id,),
            )

    def read_pending(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(str(self.db_path)) as connection:
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = ? AND name = ?",
                ("table", "desktop_view_outbox"),
            ).fetchone()
            if table is None:
                return []
            return [{"event_id": row[0], "local_id": row[1], "viewed_at": row[2]}
                    for row in connection.execute(
                        "SELECT event_id, local_id, viewed_at FROM desktop_view_outbox ORDER BY rowid"
                    ).fetchall()]

    def merge(self, rows: List[Dict[str, Any]],
              acknowledged: List[Dict[str, Any]] = None) -> Dict[str, int]:
        """首次保留桌面历史，随后只累加服务器相对上次的增量。"""
        request_id = str(uuid4())
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        changed = 0
        added = 0
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS desktop_view_sync_state (
                    local_id INTEGER PRIMARY KEY,
                    remote_id TEXT NOT NULL UNIQUE,
                    remote_count INTEGER NOT NULL CHECK(remote_count >= 0)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS desktop_view_outbox (
                    event_id TEXT PRIMARY KEY,
                    local_id INTEGER NOT NULL,
                    viewed_at TEXT NOT NULL
                )"""
            )
            pending = [{"event_id": row[0], "local_id": row[1], "viewed_at": row[2]}
                       for row in connection.execute(
                           "SELECT event_id, local_id, viewed_at FROM desktop_view_outbox ORDER BY rowid"
                       ).fetchall()]
            if pending != (acknowledged or []):
                raise ViewSyncConflict("待同步事件在服务器请求期间变更，请重试")
            local_events = {}
            for event in pending:
                local_events[event["local_id"]] = local_events.get(event["local_id"], 0) + 1
            planned = []
            for item in rows:
                local_id = item["local_id"]
                remote_id = item["remote_id"]
                count = item["view_count"]
                remote_time = item["last_viewed_at"]
                if (not isinstance(local_id, int) or isinstance(local_id, bool)
                        or not isinstance(remote_id, str) or not remote_id
                        or not isinstance(count, int) or isinstance(count, bool) or count < 0
                        or (remote_time is not None and not isinstance(remote_time, str))):
                    raise ViewSyncConflict("服务器查看统计字段无效")
                incoming = _local_time(remote_time, require_zone=True) if remote_time else None
                if (count > 0 and incoming is None) or (count == 0 and incoming is not None):
                    raise ViewSyncConflict("服务器查看次数与时间不一致")
                local = connection.execute(
                    "SELECT date, view_count, last_viewed_at FROM diaries WHERE id = ?", (local_id,)
                ).fetchone()
                if local is None or str(local["date"])[:10] != item["date"]:
                    raise ViewSyncConflict("映射的本地日记缺失或日期变化")
                if (not isinstance(local["view_count"], int) or local["view_count"] < 0):
                    raise ViewSyncConflict("本地查看次数无效")
                previous = connection.execute(
                    "SELECT remote_id, remote_count FROM desktop_view_sync_state WHERE local_id = ?",
                    (local_id,),
                ).fetchone()
                baseline = connection.execute(
                    "SELECT remote_id FROM desktop_view_baseline WHERE local_id = ?", (local_id,)
                ).fetchone()
                if not previous or not baseline or baseline["remote_id"] != remote_id:
                    raise ViewSyncConflict("查看基线尚未确认，拒绝服务器统计下行")
                if previous and (previous["remote_id"] != remote_id or count < previous["remote_count"]):
                    raise ViewSyncConflict("服务端映射或查看次数回退，未修改本地数据")
                current_time = _local_time(local["last_viewed_at"]) if local["last_viewed_at"] else None
                if local["view_count"] > 0 and current_time is None:
                    raise ViewSyncConflict("本地查看次数缺少最后查看时间")
                latest = max((time for time in (incoming, current_time) if time), default=None)
                delta = count - (previous["remote_count"] if previous else 0) - local_events.pop(local_id, 0)
                if delta < 0:
                    raise ViewSyncConflict("服务器未确认全部本地查看事件")
                planned.append((local_id, remote_id, count, delta, local["last_viewed_at"],
                                latest.strftime("%Y-%m-%d %H:%M:%S") if latest else None))
            if local_events:
                raise ViewSyncConflict("待同步事件的本地日记没有 ID 映射")
            for local_id, remote_id, count, delta, old_time, latest in planned:
                if delta or latest != old_time:
                    connection.execute(
                        "UPDATE diaries SET view_count = view_count + ?, last_viewed_at = ? WHERE id = ?",
                        (delta, latest, local_id),
                    )
                    changed += 1
                    added += delta
                connection.execute(
                    """INSERT INTO desktop_view_sync_state (local_id, remote_id, remote_count)
                       VALUES (?, ?, ?)
                       ON CONFLICT(local_id) DO UPDATE SET
                           remote_id = excluded.remote_id, remote_count = excluded.remote_count""",
                    (local_id, remote_id, count),
                )
            for event in pending:
                connection.execute("DELETE FROM desktop_view_outbox WHERE event_id = ?", (event["event_id"],))
            connection.commit()
            logger.info("桌面查看统计合并完成", extra={"request_id": request_id,
                                                  "matched": len(rows), "changed": changed, "added": added})
            return {"matched": len(rows), "changed": changed, "added": added}
        except Exception:
            connection.rollback()
            logger.exception("桌面查看统计合并回滚", extra={"request_id": request_id})
            raise
        finally:
            connection.close()