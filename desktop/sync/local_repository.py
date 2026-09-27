"""将已映射的服务器更新原子写入 PyQt 日记数据库并留下恢复记录。"""
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from utils.text_tokenizer import tokenize

from .reconcile import payload_digest

logger = logging.getLogger(__name__)


class LocalDiaryConflict(RuntimeError):
    """本地日记或恢复记录不符合预期，拒绝覆盖。"""


class LocalDiaryRepository:
    """仅更新已映射日记；游标恢复记录与内容在同一事务提交。"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        if not self.db_path.is_file():
            raise LocalDiaryConflict("本地日记数据库不存在")

    @staticmethod
    def _current(connection: sqlite3.Connection, local_id: int) -> Dict[str, Any]:
        row = connection.execute(
            "SELECT id, date, content FROM diaries WHERE id = ?", (local_id,)
        ).fetchone()
        if row is None:
            raise LocalDiaryConflict("映射的本地日记不存在")
        tags = connection.execute(
            """SELECT tags.name FROM tags
               INNER JOIN diary_tags ON diary_tags.tag_id = tags.id
               WHERE diary_tags.diary_id = ? ORDER BY tags.name""",
            (local_id,),
        ).fetchall()
        return {**dict(row), "tags": [tag["name"] for tag in tags]}

    def read_receipt(self) -> Optional[Dict[str, Any]]:
        """尚未出现下行时不创建表，也不改变用户日记库。"""
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        try:
            table = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ? AND name = ?",
                ("table", "desktop_sync_receipt"),
            ).fetchone()
            if table is None:
                return None
            row = connection.execute(
                "SELECT before_state, after_state, targets FROM desktop_sync_receipt WHERE id = ?",
                (1,),
            ).fetchone()
            if row is None:
                return None
            try:
                receipt = {name: json.loads(row[name]) for name in row.keys()}
            except (ValueError, TypeError) as exc:
                raise LocalDiaryConflict("同步恢复记录损坏") from exc
            if (not isinstance(receipt["before_state"], dict)
                    or not isinstance(receipt["after_state"], dict)
                    or not isinstance(receipt["targets"], dict)):
                raise LocalDiaryConflict("同步恢复记录结构损坏")
            before = receipt["before_state"]
            after = receipt["after_state"]
            targets = receipt["targets"]
            if (not isinstance(before.get("cursor"), int)
                    or not isinstance(after.get("cursor"), int)
                    or before["cursor"] >= after["cursor"]
                    or before.get("mapped") is not True
                    or after.get("mapped") is not True
                    or not isinstance(after.get("entries"), dict)
                    or not isinstance(before.get("entries"), dict)
                    or before["entries"].keys() != after["entries"].keys()):
                raise LocalDiaryConflict("同步恢复记录结构损坏")
            for local_id, digest in targets.items():
                entry = after["entries"].get(local_id)
                if (not isinstance(local_id, str) or not local_id.isdecimal()
                        or not isinstance(entry, dict) or not isinstance(digest, str)
                        or entry.get("payload_hash") != digest):
                    raise LocalDiaryConflict("同步恢复记录的目标内容无效")
            return receipt
        finally:
            connection.close()

    def verify_targets(self, targets: Dict[str, str]) -> None:
        """恢复前核实 SQLite 中确实保留了事务提交的目标内容。"""
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        try:
            for local_id, digest in targets.items():
                if payload_digest(self._current(connection, int(local_id))) != digest:
                    raise LocalDiaryConflict("恢复前本地日记发生变化，必须人工审核")
        finally:
            connection.close()

    def apply_updates(
        self, checks: List[Dict[str, Any]], before: Dict[str, Any], after: Dict[str, Any],
    ) -> int:
        """整页基线、日记更新及前后状态收据在一个 SQLite 事务中提交。"""
        request_id = str(uuid4())
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            for item in checks:
                current = self._current(connection, int(item["local_id"]))
                if payload_digest(current) != item["expected_hash"]:
                    raise LocalDiaryConflict("本地日记有离线修改，已停止下行覆盖")
            changed = 0
            for item in checks:
                payload = item.get("payload")
                if payload is None:
                    continue
                local_id = int(item["local_id"])
                content = payload["content"]
                updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                connection.execute(
                    "UPDATE diaries SET content = ?, tokens = ?, updated_at = ? WHERE id = ?",
                    (content, " ".join(tokenize(content)), updated_at, local_id),
                )
                connection.execute("DELETE FROM diary_tags WHERE diary_id = ?", (local_id,))
                for name in payload["tags"]:
                    connection.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
                    tag_id = connection.execute(
                        "SELECT id FROM tags WHERE name = ?", (name,)
                    ).fetchone()["id"]
                    connection.execute(
                        "INSERT INTO diary_tags (diary_id, tag_id) VALUES (?, ?)",
                        (local_id, tag_id),
                    )
                changed += 1
            targets = {
                str(item["local_id"]): payload_digest(self._current(connection, int(item["local_id"])))
                for item in checks
            }
            connection.execute(
                """CREATE TABLE IF NOT EXISTS desktop_sync_receipt (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    before_state TEXT NOT NULL,
                    after_state TEXT NOT NULL,
                    targets TEXT NOT NULL
                )"""
            )
            connection.execute(
                """INSERT INTO desktop_sync_receipt (id, before_state, after_state, targets)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       before_state = excluded.before_state,
                       after_state = excluded.after_state,
                       targets = excluded.targets""",
                (1, json.dumps(before, ensure_ascii=False, sort_keys=True),
                 json.dumps(after, ensure_ascii=False, sort_keys=True),
                 json.dumps(targets, ensure_ascii=False, sort_keys=True)),
            )
            connection.commit()
            logger.info("本地日记下行事务完成", extra={"request_id": request_id, "updated": changed})
            return changed
        except Exception:
            connection.rollback()
            logger.exception("本地日记下行事务回滚", extra={"request_id": request_id})
            raise
        finally:
            connection.close()
