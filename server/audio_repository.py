"""语音包和音频资源仓储。"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4





class AudioRepository:
    """管理语音包和音频资源。"""

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
                CREATE TABLE IF NOT EXISTS voice_profiles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    language TEXT NOT NULL,
                    voice_name TEXT NOT NULL,
                    speed REAL NOT NULL DEFAULT 1.0,
                    pitch REAL NOT NULL DEFAULT 1.0,
                    offline_supported INTEGER NOT NULL DEFAULT 0,
                    config_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audio_assets (
                    id TEXT PRIMARY KEY,
                    diary_id TEXT NOT NULL,
                    voice_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    voice_config_hash TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    format TEXT NOT NULL,
                    file_hash TEXT NOT NULL DEFAULT '',
                    file_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(diary_id, voice_id, content_hash, voice_config_hash)
                );
                CREATE INDEX IF NOT EXISTS idx_audio_assets_diary_id
                    ON audio_assets(diary_id);
                CREATE INDEX IF NOT EXISTS idx_audio_assets_status
                    ON audio_assets(status);
                """
            )

    @staticmethod
    def _record(row: sqlite3.Row) -> Dict[str, Any]:
        return dict(row)

    def ensure_voice(self, voice: Dict[str, Any]) -> Dict[str, Any]:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO voice_profiles
                (id, name, provider, language, voice_name, speed, pitch,
                 offline_supported, config_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET name = excluded.name,
                    provider = excluded.provider, language = excluded.language,
                    voice_name = excluded.voice_name, speed = excluded.speed,
                    pitch = excluded.pitch, offline_supported = excluded.offline_supported,
                    config_hash = excluded.config_hash
                """,
                (
                    voice["id"], voice["name"], voice["provider"], voice["language"],
                    voice["voice_name"], voice["speed"], voice["pitch"],
                    int(voice["offline_supported"]), voice["config_hash"], voice["created_at"],
                ),
            )
        return self.get_voice(voice["id"])

    def list_voices(self) -> List[Dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM voice_profiles ORDER BY name"
            ).fetchall()
            return [self._record(row) for row in rows]

    def get_voice(self, voice_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM voice_profiles WHERE id = ?", (voice_id,)
            ).fetchone()
            return self._record(row) if row else None

    def find_ready(
        self,
        diary_id: str,
        voice_id: str,
        content_hash: str,
        voice_config_hash: str,
    ) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM audio_assets
                WHERE diary_id = ? AND voice_id = ? AND content_hash = ?
                  AND voice_config_hash = ? AND status = 'ready'
                ORDER BY created_at DESC LIMIT 1
                """,
                (diary_id, voice_id, content_hash, voice_config_hash),
            ).fetchone()
            return self._record(row) if row else None

    def create_generating(self, record: Dict[str, Any]) -> Dict[str, Any]:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO audio_assets
                (id, diary_id, voice_id, content_hash, voice_config_hash,
                 duration_ms, format, file_hash, file_path, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(diary_id, voice_id, content_hash, voice_config_hash)
                DO UPDATE SET status = 'generating', file_path = excluded.file_path,
                              created_at = excluded.created_at
                """,
                (
                    record["id"], record["diary_id"], record["voice_id"],
                    record["content_hash"], record["voice_config_hash"], 0,
                    record["format"], "", record["file_path"], "generating",
                    record["created_at"],
                ),
            )
            row = connection.execute(
                """
                SELECT * FROM audio_assets
                WHERE diary_id = ? AND voice_id = ? AND content_hash = ?
                  AND voice_config_hash = ?
                """,
                (
                    record["diary_id"], record["voice_id"], record["content_hash"],
                    record["voice_config_hash"],
                ),
            ).fetchone()
            return self._record(row)

    def mark_ready(self, asset_id: str, duration_ms: int, file_hash: str) -> Dict[str, Any]:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE audio_assets
                SET duration_ms = ?, file_hash = ?, status = 'ready'
                WHERE id = ?
                """,
                (duration_ms, file_hash, asset_id),
            )
        return self.get_asset(asset_id)

    def mark_failed(self, asset_id: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE audio_assets SET status = 'failed' WHERE id = ?",
                (asset_id,),
            )

    def expire_for_diary(self, diary_id: str, content_hash: str) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE audio_assets SET status = 'expired'
                WHERE diary_id = ? AND content_hash <> ? AND status IN ('ready', 'generating')
                """,
                (diary_id, content_hash),
            )

    def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM audio_assets WHERE id = ?", (asset_id,)
            ).fetchone()
            return self._record(row) if row else None

    def list_assets(self, diary_id: str) -> List[Dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM audio_assets
                WHERE diary_id = ? AND status = 'ready'
                ORDER BY created_at DESC
                """,
                (diary_id,),
            ).fetchall()
            return [self._record(row) for row in rows]

    @staticmethod
    def new_id() -> str:
        """生成音频资源 ID。"""
        return str(uuid4())

