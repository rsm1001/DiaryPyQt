"""服务端测试共用脚手架：测试配置与假 TTS。"""
from pathlib import Path

from server.audio_repository import AudioRepository
from server.audio_service import AudioService
from server.config.settings import Settings
from server.repository import DiaryRepository
from server.service import DiaryService


class FakeTTSProvider:
    """写入可验证的测试音频内容。"""

    async def synthesize(self, text, output_path, voice):
        output_path.write_bytes(f"audio:{text}".encode("utf-8"))
        return 1234


def build_settings(temp_dir):
    """创建测试配置。"""
    return Settings(
        host="test-host",
        port=8010,
        db_path=Path(temp_dir) / "diary.db",
        audio_root=Path(temp_dir) / "audio",
        default_voice_name="test-voice",
        allowed_origins=["*"],
    )


def build_audio_service(settings):
    """创建使用测试 TTS 的音频服务。"""
    diary_service = DiaryService(DiaryRepository(settings.db_path))
    return diary_service, AudioService(
        diary_service=diary_service,
        audio_repository=AudioRepository(settings.db_path),
        provider=FakeTTSProvider(),
        audio_root=settings.audio_root,
        default_voice_name=settings.default_voice_name,
    )
