"""
垃圾桶两阶段提交（2PC）协调器

三阶段协议：
    1) precommit  : 在主库 + 垃圾桶库各写一行 pending（state='pending'）
    2) apply      : 在主库做"真实写"（move=DELETE, restore=INSERT），state='applied'
    3) commit     : 在垃圾桶库做"真实写"（move=INSERT, restore=DELETE），state='committed'

崩溃恢复（recover_pending_ops，启动时调用一次）：
    - state='committed'           -> 无事可做
    - state='applied' (两库一致)  -> 走 phase 3 commit
    - state='pending' (两库一致)  -> 删除两侧 pending（无副作用回滚）
    - 状态不一致                 -> 以主库为准，垃圾桶库补齐后重放

设计要点：
- 主库侧通过 duck-typed MainDb 协议访问（不依赖具体类，便于单元测试 mock）
- 所有 SQL 写入均显式 BEGIN/COMMIT/ROLLBACK，与外层 _transaction() 嵌套无副作用
"""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Tuple

from .connection import TrashConnectionPool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 主库协议（duck-typed）
# ---------------------------------------------------------------------------

class MainDbLike(Protocol):
    """主库需对外暴露的最小接口，供 2PC 协调器依赖注入。"""
    @property
    def db_path(self) -> str: ...
    @property
    def _db_lock(self) -> Any: ...
    def _transaction(self): ...
    def _execute(
        self,
        query: str,
        params: Tuple = (),
        fetch: Optional[str] = None,
    ) -> Optional[Any]: ...
    def compute_tokens(self, content: str) -> str: ...
    def get_tag_by_id(self, tag_id: int) -> Optional[Dict[str, Any]]: ...
    def get_tag_by_name(self, name: str) -> Optional[Dict[str, Any]]: ...
    def add_tag(self, name: str) -> Optional[Dict[str, Any]]: ...
    def get_tags_by_diary_id(self, diary_id: int) -> List[Dict[str, Any]]: ...
    def get_diary_by_id(self, diary_id: int) -> Optional[Dict[str, Any]]: ...


# ---------------------------------------------------------------------------
# 2PC 协调器
# ---------------------------------------------------------------------------

class TrashTwoPhaseCommitCoordinator:
    """垃圾桶 2PC 协调器（move / restore 跨库事务）"""

    VALID_OP_TYPES = ('move', 'restore')

    def __init__(
        self,
        connection_pool: TrashConnectionPool,
        main_db: MainDbLike,
    ):
        self._pool = connection_pool
        self._main_db = main_db

    # ------------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------------

    def precommit(
        self,
        op_id: str,
        op_type: str,
        diary_id: Optional[int],
        trash_id: Optional[int],
        payload: Dict[str, Any],
    ) -> None:
        """阶段 1：在两库各写一行 pending（state=pending）"""
        self._validate_op_type(op_type)
        now = self._now()
        payload_text = self._serialize_payload(payload)
        params = (op_id, op_type, diary_id, trash_id, payload_text, now, now)

        # 主库写 pending
        with self._main_db._transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO pending_trash_ops
                (op_id, op_type, diary_id, trash_id, payload, state, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                params,
            )

        # 垃圾桶库写 pending
        with self._pool.lock:
            trash_cursor = self._pool.connection.cursor()
            try:
                trash_cursor.execute("BEGIN")
                trash_cursor.execute(
                    """
                    INSERT INTO pending_trash_ops
                    (op_id, op_type, diary_id, trash_id, payload, state, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    params,
                )
                self._pool.connection.commit()
            except Exception:
                self._pool.connection.rollback()
                raise

    def apply_to_main(
        self,
        op_id: str,
        op_type: str,
        diary_id: Optional[int],
        trash_id: Optional[int],
        payload: Dict[str, Any],
    ) -> None:
        """阶段 2：在主库做"真实写"，并把两库 state 标 'applied'

        - move   : DELETE FROM diaries WHERE id = ?
        - restore: INSERT INTO diaries (...) VALUES (...)
        """
        self._validate_op_type(op_type)
        now = self._now()

        with self._main_db._transaction() as cursor:
            self._apply_main_write(cursor, op_type, diary_id, payload)
            cursor.execute(
                "UPDATE pending_trash_ops SET state = 'applied', updated_at = ? "
                "WHERE op_id = ?",
                (now, op_id),
            )

        # 同步垃圾桶库的 state
        with self._pool.lock:
            trash_cursor = self._pool.connection.cursor()
            try:
                trash_cursor.execute("BEGIN")
                trash_cursor.execute(
                    "UPDATE pending_trash_ops SET state = 'applied', updated_at = ? "
                    "WHERE op_id = ?",
                    (now, op_id),
                )
                self._pool.connection.commit()
            except Exception:
                self._pool.connection.rollback()
                raise

    def commit_to_trash(
        self,
        op_id: str,
        op_type: str,
        diary_id: Optional[int],
        trash_id: Optional[int],
        payload: Dict[str, Any],
    ) -> None:
        """阶段 3：在垃圾桶库做"真实写"，并把两库 state 标 'committed'

        - move   : INSERT INTO trash_diaries/trash_tags
        - restore: DELETE FROM trash_diaries WHERE id = ?
        """
        self._validate_op_type(op_type)
        now = self._now()

        with self._pool.lock:
            trash_cursor = self._pool.connection.cursor()
            try:
                trash_cursor.execute("BEGIN")
                self._apply_trash_write(trash_cursor, op_type, diary_id, trash_id, payload)
                trash_cursor.execute(
                    "UPDATE pending_trash_ops SET state = 'committed', updated_at = ? "
                    "WHERE op_id = ?",
                    (now, op_id),
                )
                self._pool.connection.commit()
            except Exception:
                self._pool.connection.rollback()
                raise

        # 同步主库的 state
        with self._main_db._transaction() as cursor:
            cursor.execute(
                "UPDATE pending_trash_ops SET state = 'committed', updated_at = ? "
                "WHERE op_id = ?",
                (now, op_id),
            )

    # ------------------------------------------------------------------
    # 启动恢复
    # ------------------------------------------------------------------

    def recover_pending_ops(self) -> int:
        """扫描两库 pending_trash_ops，推进到稳定态

        Returns:
            恢复/清理的 op 数量
        """
        main_rows = self._read_main_pending()
        trash_rows = self._read_trash_pending()

        main_by_id = {r['op_id']: r for r in main_rows}
        trash_by_id = {r['op_id']: r for r in trash_rows}
        all_op_ids = set(main_by_id) | set(trash_by_id)

        recovered = 0
        for op_id in all_op_ids:
            m = main_by_id.get(op_id)
            t = trash_by_id.get(op_id)

            # 主库已 committed -> 垃圾桶库可能漏写 phase 3
            if m and m['state'] == 'committed' and (not t or t['state'] != 'committed'):
                if self._replay_commit(m, op_id, "主库已 committed"):
                    recovered += 1
                continue

            # 两库都 applied -> 重放阶段 3
            if m and t and m['state'] == 'applied' and t['state'] == 'applied':
                if self._replay_commit(m, op_id, "两库 applied"):
                    recovered += 1
                continue

            # 两库都 pending -> 安全清理（无副作用）
            if (not m or m['state'] == 'pending') and (not t or t['state'] == 'pending'):
                self.cleanup_pending_op(op_id)
                logger.info("2PC 恢复: %s 阶段1 pending 清理", op_id)
                recovered += 1
                continue

            # 其他不一致情形 -> 以主库为准：把垃圾桶库对齐到主库
            if m and not t:
                self.mirror_pending_to_trash(m)
                logger.info("2PC 恢复: %s 补齐垃圾桶库 pending 行", op_id)
            elif t and not m:
                self.mirror_pending_to_main(t)
                logger.info("2PC 恢复: %s 补齐主库 pending 行", op_id)

        return recovered

    # ------------------------------------------------------------------
    # 跨库镜像 / 清理
    # ------------------------------------------------------------------

    def cleanup_pending_op(self, op_id: str) -> None:
        """删除两库指定 op_id 的 pending 行（任一失败不影响另一库）"""
        try:
            with self._main_db._transaction() as cursor:
                cursor.execute(
                    "DELETE FROM pending_trash_ops WHERE op_id = ?", (op_id,)
                )
        except Exception as exc:
            logger.warning("清理主库 pending 失败 %s: %s", op_id, exc)
        try:
            with self._pool.lock:
                trash_cursor = self._pool.connection.cursor()
                trash_cursor.execute("BEGIN")
                trash_cursor.execute(
                    "DELETE FROM pending_trash_ops WHERE op_id = ?", (op_id,)
                )
                self._pool.connection.commit()
        except Exception as exc:
            logger.warning("清理垃圾桶库 pending 失败 %s: %s", op_id, exc)

    def mirror_pending_to_trash(self, main_row: Dict[str, Any]) -> None:
        """把主库的 pending 行镜像到垃圾桶库（INSERT OR REPLACE）"""
        now = self._now()
        with self._pool.lock:
            trash_cursor = self._pool.connection.cursor()
            try:
                trash_cursor.execute("BEGIN")
                trash_cursor.execute(
                    """
                    INSERT OR REPLACE INTO pending_trash_ops
                    (op_id, op_type, diary_id, trash_id, payload, state,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, ''), ?)
                    """,
                    (
                        main_row['op_id'],
                        main_row['op_type'],
                        main_row['diary_id'],
                        main_row['trash_id'],
                        main_row['payload'],
                        main_row['state'],
                        main_row.get('created_at') or '',
                        main_row.get('updated_at') or now,
                    ),
                )
                self._pool.connection.commit()
            except Exception:
                self._pool.connection.rollback()
                raise

    def mirror_pending_to_main(self, trash_row: Dict[str, Any]) -> None:
        """把垃圾桶库的 pending 行镜像到主库（INSERT OR REPLACE）"""
        now = self._now()
        with self._main_db._transaction() as cursor:
            cursor.execute(
                """
                INSERT OR REPLACE INTO pending_trash_ops
                (op_id, op_type, diary_id, trash_id, payload, state,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, ''), ?)
                """,
                (
                    trash_row['op_id'],
                    trash_row['op_type'],
                    trash_row['diary_id'],
                    trash_row['trash_id'],
                    trash_row['payload'],
                    trash_row['state'],
                    trash_row.get('created_at') or '',
                    trash_row.get('updated_at') or now,
                ),
            )

    # ------------------------------------------------------------------
    # op_id 生成
    # ------------------------------------------------------------------

    @staticmethod
    def new_op_id() -> str:
        """生成全局唯一 op_id（uuid4 字符串）"""
        return str(uuid.uuid4())

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _validate_op_type(self, op_type: str) -> None:
        if op_type not in self.VALID_OP_TYPES:
            raise ValueError(f"未知 op_type: {op_type!r}")

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _serialize_payload(payload: Dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, default=str)

    def _apply_main_write(
        self,
        cursor,
        op_type: str,
        diary_id: Optional[int],
        payload: Dict[str, Any],
    ) -> None:
        """阶段 2 真实写（主库）"""
        if op_type == 'move':
            cursor.execute("DELETE FROM diaries WHERE id = ?", (diary_id,))
            return

        if op_type == 'restore':
            cursor.execute(
                """
                INSERT INTO diaries
                (date, content, view_count, last_viewed_at, tokens, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload['date'],
                    payload['content'],
                    payload.get('view_count', 0),
                    payload.get('last_viewed_at'),
                    payload.get('tokens', ''),
                    payload.get('updated_at'),
                ),
            )
            for tag in payload.get('tags', []):
                tag_id = self._resolve_tag_id(tag)
                if tag_id:
                    cursor.execute(
                        "INSERT OR IGNORE INTO diary_tags (diary_id, tag_id) "
                        "VALUES (?, ?)",
                        (cursor.lastrowid, tag_id),
                    )
            return

    def _apply_trash_write(
        self,
        cursor,
        op_type: str,
        diary_id: Optional[int],
        trash_id: Optional[int],
        payload: Dict[str, Any],
    ) -> None:
        """阶段 3 真实写（垃圾桶库）"""
        if op_type == 'move':
            deleted_at = self._now()
            cursor.execute(
                """
                INSERT INTO trash_diaries
                (original_id, date, deleted_at, content, view_count,
                 last_viewed_at, source_db_path, tokens, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    diary_id,
                    payload['date'],
                    deleted_at,
                    payload['content'],
                    payload.get('view_count', 0),
                    payload.get('last_viewed_at'),
                    os.path.abspath(self._main_db.db_path),
                    payload.get('tokens', ''),
                    payload.get('updated_at'),
                ),
            )
            new_trash_id = cursor.lastrowid
            for tag in payload.get('tags', []):
                cursor.execute(
                    "INSERT INTO trash_tags "
                    "(trash_diary_id, name, original_tag_id) VALUES (?, ?, ?)",
                    (new_trash_id, tag['name'], tag.get('original_tag_id')),
                )
            return

        if op_type == 'restore':
            cursor.execute(
                "DELETE FROM trash_diaries WHERE id = ?", (trash_id,)
            )
            return

    def _resolve_tag_id(self, tag: Dict[str, Any]) -> Optional[int]:
        """恢复时解析 tag_id：优先按 original_tag_id，再按 name"""
        if tag.get('original_tag_id'):
            existing = self._main_db.get_tag_by_id(tag['original_tag_id'])
            if existing:
                return existing['id']
        if tag.get('name'):
            existing_by_name = self._main_db.get_tag_by_name(tag['name'])
            if existing_by_name:
                return existing_by_name['id']
            new_tag = self._main_db.add_tag(tag['name'])
            if new_tag:
                return new_tag['id']
        return None

    def _replay_commit(
        self,
        row: Dict[str, Any],
        op_id: str,
        reason: str,
    ) -> bool:
        payload = self._deserialize_payload(row['payload'])
        try:
            self.commit_to_trash(
                op_id, row['op_type'], row['diary_id'], row['trash_id'], payload,
            )
            logger.info("2PC 恢复: %s 阶段3 重放 (%s)", op_id, reason)
            return True
        except Exception as exc:
            logger.error("2PC 恢复失败 %s: %s", op_id, exc)
            return False

    @staticmethod
    def _deserialize_payload(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, str):
            return json.loads(raw)
        return raw

    def _read_main_pending(self) -> List[Dict[str, Any]]:
        try:
            return self._main_db._execute(
                "SELECT op_id, op_type, diary_id, trash_id, payload, state, "
                "created_at, updated_at "
                "FROM pending_trash_ops",
                fetch='all',
            ) or []
        except Exception as exc:
            logger.warning("读取主库 pending_trash_ops 失败: %s", exc)
            return []

    def _read_trash_pending(self) -> List[Dict[str, Any]]:
        try:
            with self._pool.lock:
                cursor = self._pool.connection.cursor()
                cursor.execute(
                    "SELECT op_id, op_type, diary_id, trash_id, payload, state, "
                    "created_at, updated_at "
                    "FROM pending_trash_ops"
                )
                return [dict(r) for r in cursor.fetchall()]
        except Exception as exc:
            logger.warning("读取垃圾桶库 pending_trash_ops 失败: %s", exc)
            return []
