"""日记数据库仓储。"""
from contextlib import contextmanager
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from server.logging_config import get_logger


logger = get_logger("diary.repository")


class DiaryRepository:
    """使用 SQLite 保存日记和标签。"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
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
                CREATE TABLE IF NOT EXISTS diaries (
                    id TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    deleted_at TEXT
                );
                CREATE TABLE IF NOT EXISTS tags (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS diary_tags (
                    diary_id TEXT NOT NULL,
                    tag_id TEXT NOT NULL,
                    PRIMARY KEY (diary_id, tag_id),
                    FOREIGN KEY (diary_id) REFERENCES diaries(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_diaries_date ON diaries(date);
                CREATE INDEX IF NOT EXISTS idx_diaries_updated_at ON diaries(updated_at);
                CREATE INDEX IF NOT EXISTS idx_diary_tags_tag_id ON diary_tags(tag_id);
                CREATE TABLE IF NOT EXISTS diary_views (
                    diary_id TEXT PRIMARY KEY,
                    view_count INTEGER NOT NULL DEFAULT 0,
                    last_viewed_at TEXT,
                    FOREIGN KEY (diary_id) REFERENCES diaries(id) ON DELETE CASCADE
                );
                """
            )

    @staticmethod
    def _tags(connection: sqlite3.Connection, diary_id: str) -> List[str]:
        rows = connection.execute(
            """
            SELECT tags.name FROM tags
            INNER JOIN diary_tags ON diary_tags.tag_id = tags.id
            WHERE diary_tags.diary_id = ?
            ORDER BY tags.name
            """,
            (diary_id,),
        ).fetchall()
        return [row["name"] for row in rows]

    @classmethod
    def _record(cls, connection: sqlite3.Connection, row: sqlite3.Row) -> Dict[str, Any]:
        record = dict(row)
        record["tags"] = cls._tags(connection, record["id"])
        view_row = connection.execute(
            "SELECT view_count, last_viewed_at FROM diary_views WHERE diary_id = ?",
            (record["id"],),
        ).fetchone()
        record["view_count"] = int(view_row["view_count"]) if view_row else 0
        record["last_viewed_at"] = view_row["last_viewed_at"] if view_row else None
        return record

    @staticmethod
    def _replace_tags(connection: sqlite3.Connection, diary_id: str, tags: List[str], now: str) -> None:
        connection.execute("DELETE FROM diary_tags WHERE diary_id = ?", (diary_id,))
        for name in sorted(set(tag.strip() for tag in tags if tag.strip())):
            tag_id = str(uuid4())
            connection.execute(
                "INSERT OR IGNORE INTO tags (id, name, created_at) VALUES (?, ?, ?)",
                (tag_id, name, now),
            )
            tag_row = connection.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
            connection.execute(
                "INSERT INTO diary_tags (diary_id, tag_id) VALUES (?, ?)",
                (diary_id, tag_row["id"]),
            )

    def list_diaries(self, include_deleted: bool, limit: int, offset: int) -> List[Dict[str, Any]]:
        with self._connection() as connection:
            if include_deleted:
                rows = connection.execute(
                    "SELECT * FROM diaries ORDER BY date DESC, created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM diaries
                    WHERE deleted_at IS NULL
                    ORDER BY date DESC, created_at DESC LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                ).fetchall()
            return [self._record(connection, row) for row in rows]

    def list_deleted_diaries(self, limit: int, offset: int) -> List[Dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT * FROM diaries WHERE deleted_at IS NOT NULL
                   ORDER BY deleted_at DESC LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
            return [self._record(connection, row) for row in rows]

    def restore(self, diary_id: str, expected_version: Optional[int]) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT version FROM diaries WHERE id = ? AND deleted_at IS NOT NULL",
                (diary_id,),
            ).fetchone()
            if row is None or (expected_version is not None and row["version"] != expected_version):
                return None
            connection.execute(
                "UPDATE diaries SET deleted_at = NULL, updated_at = datetime('now'), version = version + 1 WHERE id = ?",
                (diary_id,),
            )
            row = connection.execute("SELECT * FROM diaries WHERE id = ?", (diary_id,)).fetchone()
            return self._record(connection, row)

    def permanently_delete(self, diary_id: str) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM diaries WHERE id = ? AND deleted_at IS NOT NULL", (diary_id,)
            ).fetchone()
            if row is None:
                return False
            connection.execute("DELETE FROM audio_assets WHERE diary_id = ?", (diary_id,))
            connection.execute("DELETE FROM diaries WHERE id = ? AND deleted_at IS NOT NULL", (diary_id,))
            return True

    def record_view(self, diary_id: str, viewed_at: str) -> Dict[str, Any]:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO diary_views (diary_id, view_count, last_viewed_at)
                   VALUES (?, 1, ?)
                   ON CONFLICT(diary_id) DO UPDATE SET
                       view_count = diary_views.view_count + 1,
                       last_viewed_at = excluded.last_viewed_at""",
                (diary_id, viewed_at),
            )
            row = connection.execute(
                "SELECT view_count, last_viewed_at FROM diary_views WHERE diary_id = ?",
                (diary_id,),
            ).fetchone()
            return {"diary_id": diary_id, "view_count": int(row["view_count"]),
                    "viewed_at": row["last_viewed_at"]}

    def view_statistics(self) -> Dict[str, Any]:
        with self._connection() as connection:
            summary = connection.execute(
                """SELECT COUNT(*) AS total_diaries,
                          COALESCE(SUM(COALESCE(diary_views.view_count, 0)), 0) AS total_views,
                          COALESCE(AVG(COALESCE(diary_views.view_count, 0)), 0) AS average_views
                   FROM diaries
                   LEFT JOIN diary_views ON diary_views.diary_id = diaries.id
                   WHERE diaries.deleted_at IS NULL"""
            ).fetchone()
            most = connection.execute(
                """SELECT diaries.id, COALESCE(diary_views.view_count, 0) AS view_count
                   FROM diaries
                   LEFT JOIN diary_views ON diary_views.diary_id = diaries.id
                   WHERE diaries.deleted_at IS NULL
                   ORDER BY view_count DESC, diaries.updated_at DESC LIMIT 1"""
            ).fetchone()
            least = connection.execute(
                """SELECT diaries.id, COALESCE(diary_views.view_count, 0) AS view_count
                   FROM diaries
                   LEFT JOIN diary_views ON diary_views.diary_id = diaries.id
                   WHERE diaries.deleted_at IS NULL
                   ORDER BY view_count ASC, diaries.updated_at DESC LIMIT 1"""
            ).fetchone()
            return {
                "total_diaries": int(summary["total_diaries"]),
                "total_views": int(summary["total_views"]),
                "average_views": float(summary["average_views"]),
                "most_viewed_id": most["id"] if most else None,
                "most_viewed_count": int(most["view_count"]) if most else 0,
                "least_viewed_id": least["id"] if least else None,
                "least_viewed_count": int(least["view_count"]) if least else 0,
            }

    def get(self, diary_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM diaries WHERE id = ?", (diary_id,)).fetchone()
            return self._record(connection, row) if row else None

    def create(self, record: Dict[str, Any]) -> Dict[str, Any]:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO diaries
                (id, date, content, content_hash, version, created_at, updated_at, deleted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["id"], record["date"], record["content"], record["content_hash"],
                    record["version"], record["created_at"], record["updated_at"], record["deleted_at"],
                ),
            )
            self._replace_tags(connection, record["id"], record["tags"], record["created_at"])
            logger.info("diary_created", extra={"diary_id": record["id"]})
        return self.get(record["id"])

    def update(self, diary_id: str, record: Dict[str, Any], expected_version: int) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE diaries
                SET date = ?, content = ?, content_hash = ?, updated_at = ?, version = version + 1
                WHERE id = ? AND version = ? AND deleted_at IS NULL
                """,
                (
                    record["date"], record["content"], record["content_hash"],
                    record["updated_at"], diary_id, expected_version,
                ),
            )
            if cursor.rowcount == 0:
                return False
            self._replace_tags(connection, diary_id, record["tags"], record["updated_at"])
            logger.info("diary_updated", extra={"diary_id": diary_id})
            return True

    def delete(self, diary_id: str, deleted_at: str, expected_version: int) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE diaries
                SET deleted_at = ?, updated_at = ?, version = version + 1
                WHERE id = ? AND version = ? AND deleted_at IS NULL
                """,
                (deleted_at, deleted_at, diary_id, expected_version),
            )
            if cursor.rowcount:
                logger.info("diary_deleted", extra={"diary_id": diary_id})
            return bool(cursor.rowcount)

    def get_tag(self, tag_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT id, name, created_at FROM tags WHERE id = ?", (tag_id,)
            ).fetchone()
            return dict(row) if row else None

    def create_tag(self, name: str) -> Dict[str, Any]:
        normalized = name.strip()
        if not normalized:
            raise ValueError("????????")
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT id, name, created_at FROM tags WHERE name = ?", (normalized,)
            ).fetchone()
            if existing:
                return dict(existing)
            tag_id = str(uuid4())
            connection.execute(
                "INSERT INTO tags (id, name, created_at) VALUES (?, ?, datetime('now'))",
                (tag_id, normalized),
            )
            row = connection.execute(
                "SELECT id, name, created_at FROM tags WHERE id = ?", (tag_id,)
            ).fetchone()
            return dict(row)

    def update_tag(self, tag_id: str, name: str) -> Optional[Dict[str, Any]]:
        normalized = name.strip()
        if not normalized:
            raise ValueError("????????")
        with self._connection() as connection:
            try:
                cursor = connection.execute(
                    "UPDATE tags SET name = ? WHERE id = ?", (normalized, tag_id)
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("???????") from exc
            if cursor.rowcount == 0:
                return None
            row = connection.execute(
                "SELECT id, name, created_at FROM tags WHERE id = ?", (tag_id,)
            ).fetchone()
            return dict(row)

    def delete_tag(self, tag_id: str) -> bool:
        with self._connection() as connection:
            used = connection.execute(
                """SELECT 1 FROM diary_tags
                   INNER JOIN diaries ON diaries.id = diary_tags.diary_id
                   WHERE diary_tags.tag_id = ? AND diaries.deleted_at IS NULL
                   LIMIT 1""",
                (tag_id,),
            ).fetchone()
            if used:
                return False
            cursor = connection.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
            return bool(cursor.rowcount)

    def list_tags(self) -> List[Dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id, name, created_at FROM tags ORDER BY name"
            ).fetchall()
            return [dict(row) for row in rows]

