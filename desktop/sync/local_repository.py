"""将已映射的服务器更新原子写入 PyQt 日记数据库并留下恢复记录。"""
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from utils.text_tokenizer import tokenize

from .reconcile import canonical_payload, payload_digest

logger = logging.getLogger(__name__)

DESKTOP_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


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
                    # 服务器新日记会在同一页里新增映射，因此只要求旧映射被完整保留
                    or not set(before["entries"].keys()).issubset(after["entries"].keys())):
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

    def clear_receipt(self) -> None:
        """状态已完整落盘后清除收据。

        收据的适用范围只到"SQLite 已提交、状态文件未保存"；状态一旦保存，
        收据即作废，否则下一轮会把它误判成"与磁盘状态不一致"。
        """
        connection = sqlite3.connect(str(self.db_path))
        try:
            table = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ? AND name = ?",
                ("table", "desktop_sync_receipt"),
            ).fetchone()
            if table is None:
                return
            connection.execute("DELETE FROM desktop_sync_receipt WHERE id = 1")
            connection.commit()
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

    def trash_db_path(self) -> Path:
        """垃圾桶库与主库同目录，命名规则与 TrashConnectionPool 保持一致。"""
        return self.db_path.with_name(f"trash_{self.db_path.stem}.db")

    def trash_deleted_at(self, local_id: int) -> Optional[str]:
        """读取回收站记录的删除时间。

        用于"本地删除 vs 服务器后续编辑"的时间比较。回收站有容量淘汰，
        记录可能已被清掉，取不到时返回 None，由调用方降级为删除优先。
        """
        trash_path = self.trash_db_path()
        if not trash_path.is_file():
            return None
        connection = sqlite3.connect(str(trash_path))
        connection.row_factory = sqlite3.Row
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = ? AND name = ?",
                ("table", "trash_diaries"),
            ).fetchone()
            if table is None:
                return None
            row = connection.execute(
                "SELECT deleted_at FROM trash_diaries WHERE original_id = ? "
                "ORDER BY deleted_at DESC LIMIT 1", (local_id,),
            ).fetchone()
            return row["deleted_at"] if row else None
        finally:
            connection.close()

    def snapshot_with_tags(self) -> Dict[int, Dict[str, Any]]:
        """读取本地全量快照（含标签名），供一轮同步做差异比对。"""
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        try:
            tags: Dict[int, List[str]] = {}
            for row in connection.execute(
                """SELECT diary_tags.diary_id AS diary_id, tags.name AS name
                   FROM diary_tags INNER JOIN tags ON tags.id = diary_tags.tag_id
                   ORDER BY tags.name"""
            ):
                tags.setdefault(row["diary_id"], []).append(row["name"])
            snapshot: Dict[int, Dict[str, Any]] = {}
            for row in connection.execute(
                "SELECT id, date, content, updated_at FROM diaries ORDER BY id"
            ):
                snapshot[row["id"]] = {
                    "id": row["id"], "date": row["date"], "content": row["content"],
                    "updated_at": row["updated_at"], "tags": tags.get(row["id"], []),
                }
            return snapshot
        finally:
            connection.close()

    @staticmethod
    def _bind_names(cursor: sqlite3.Cursor, local_id: int, tags: List[str]) -> None:
        """按标签名绑定关系；tags 只有名称，id 由主库分配。"""
        cursor.execute("DELETE FROM diary_tags WHERE diary_id = ?", (local_id,))
        for name in tags:
            cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
            tag_id = cursor.execute(
                "SELECT id FROM tags WHERE name = ?", (name,)
            ).fetchone()["id"]
            cursor.execute(
                "INSERT INTO diary_tags (diary_id, tag_id) VALUES (?, ?)", (local_id, tag_id)
            )

    def adopt_or_create(self, payload: Dict[str, Any], desktop_date: str,
                        local_updated_at: str,
                        candidates: Dict[int, Dict[str, Any]]) -> int:
        """把服务器日记写进本地，返回本地 ID。

        candidates 是尚未建立映射的本地日记。若其中恰好有一篇内容完全相同，
        直接采纳它而不是新建：这样"回收站恢复后换了新 ID"不会在服务器上
        再生成一份重复日记。
        """
        matched = [local_id for local_id, row in candidates.items()
                   if canonical_payload(row) == payload]
        if len(matched) > 1:
            raise LocalDiaryConflict("本地有多篇相同内容，无法确定对应关系")
        if matched:
            return matched[0]

        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "INSERT INTO diaries (date, content, tokens, updated_at) VALUES (?, ?, ?, ?)",
                (desktop_date, payload["content"], " ".join(tokenize(payload["content"])),
                 local_updated_at),
            )
            local_id = int(cursor.lastrowid)
            self._bind_names(connection.cursor(), local_id, payload["tags"])
            connection.commit()
            logger.info("服务器日记已写入本地", extra={"request_id": str(uuid4()), "local_id": local_id})
            return local_id
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def restore_with_local_id(self, local_id: int, payload: Dict[str, Any],
                              desktop_date: str, local_updated_at: str) -> None:
        """用原本地 ID 重新插入服务器版本，保住既有映射。

        本地删除后服务器又更新时走这里；AUTOINCREMENT 保证旧 ID 不会被复用。
        """
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT 1 FROM diaries WHERE id = ?", (local_id,)
            ).fetchone()
            if existing is not None:
                raise LocalDiaryConflict("本地已存在该 ID，拒绝重复插入")
            connection.execute(
                "INSERT INTO diaries (id, date, content, tokens, updated_at) VALUES (?, ?, ?, ?, ?)",
                (local_id, desktop_date, payload["content"],
                 " ".join(tokenize(payload["content"])), local_updated_at),
            )
            self._bind_names(connection.cursor(), local_id, payload["tags"])
            connection.commit()
            logger.info("服务器日记已用原本地 ID 恢复", extra={"request_id": str(uuid4()),
                                                       "local_id": local_id})
        except Exception:
            connection.rollback()
            raise
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
                # 用服务器时间回写：用 now() 会让下一轮把自己的落地误判成"本地新修改"
                updated_at = item.get("updated_at") or datetime.now().strftime(DESKTOP_TIME_FORMAT)
                connection.execute(
                    "UPDATE diaries SET content = ?, tokens = ?, updated_at = ? WHERE id = ?",
                    (content, " ".join(tokenize(content)), updated_at, local_id),
                )
                self._bind_names(connection.cursor(), local_id, payload["tags"])
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
