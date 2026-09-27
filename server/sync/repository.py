"""同步和播放记录仓储。"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


class SyncRepository:
    """保存同步变更游标和播放状态。"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize_schema(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sync_changes (
                    cursor INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS playback_records (
                    id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    diary_id TEXT NOT NULL,
                    voice_id TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    position_ms INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_playback_device_diary_voice
                    ON playback_records(device_id, diary_id, voice_id);
                CREATE INDEX IF NOT EXISTS idx_sync_changes_cursor
                    ON sync_changes(cursor);
                CREATE INDEX IF NOT EXISTS idx_playback_device_diary
                    ON playback_records(device_id, diary_id);
                """
            )

    def record_change(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        version: int,
        updated_at: str,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO sync_changes
                (entity_type, entity_id, action, version, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (entity_type, entity_id, action, version, updated_at),
            )

    def pull_changes(self, cursor: int, limit: int) -> List[Dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT cursor, entity_type, entity_id, action, version, updated_at
                FROM sync_changes
                WHERE cursor > ?
                ORDER BY cursor
                LIMIT ?
                """,
                (cursor, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def save_playback(self, record: Dict[str, Any]) -> Dict[str, Any]:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO playback_records
                (id, device_id, diary_id, voice_id, round_number, position_ms, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id, diary_id, voice_id) DO UPDATE SET id = excluded.id,
                    position_ms = excluded.position_ms, round_number = excluded.round_number,
                    status = excluded.status, updated_at = excluded.updated_at
                """,
                (
                    record.get("id") or str(uuid4()), record["device_id"], record["diary_id"],
                    record["voice_id"], record["round_number"], record["position_ms"],
                    record["status"], record["updated_at"],
                ),
            )
            row = connection.execute(
                """
                SELECT * FROM playback_records
                WHERE device_id = ? AND diary_id = ? AND voice_id = ?
                """,
                (record["device_id"], record["diary_id"], record["voice_id"]),
            ).fetchone()
            return dict(row)

    def get_playback(self, device_id: str, diary_id: str, voice_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM playback_records
                WHERE device_id = ? AND diary_id = ? AND voice_id = ?
                """,
                (device_id, diary_id, voice_id),
            ).fetchone()
            return dict(row) if row else None
