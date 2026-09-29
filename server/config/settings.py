"""日记后端运行配置。"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """日记后端配置。"""

    host: str
    port: int
    db_path: Path
    audio_root: Path
    default_voice_name: str
    allowed_origins: List[str]
    audio_generation_timeout_seconds: int = 90


def get_settings() -> Settings:
    """从环境变量读取运行配置。"""
    load_dotenv()
    server_root = Path(__file__).resolve().parents[1]
    default_db_path = server_root / "data" / "diary_server.db"
    default_audio_root = server_root / "data" / "audio"
    origins = os.getenv("DIARY_ALLOWED_ORIGINS", "*")
    return Settings(
        host=os.getenv("DIARY_API_HOST", "127.0.0.1"),
        port=int(os.getenv("DIARY_API_PORT", "8010")),
        db_path=Path(os.getenv("DIARY_DB_PATH", str(default_db_path))),
        audio_root=Path(os.getenv("DIARY_AUDIO_ROOT", str(default_audio_root))),
        default_voice_name=os.getenv("DIARY_DEFAULT_VOICE_NAME", "zh-CN-XiaoxiaoNeural"),
        allowed_origins=[item.strip() for item in origins.split(",") if item.strip()],
        audio_generation_timeout_seconds=int(
            os.getenv("DIARY_AUDIO_GENERATION_TIMEOUT_SECONDS", "90")
        ),
    )
