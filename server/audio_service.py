"""日记音频业务服务。"""
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import NAMESPACE_URL, uuid4, uuid5

from server.audio_provider import TTSProvider
from server.audio_repository import AudioRepository
from server.logging_config import get_logger
from server.service import DiaryService, ServiceError, utc_now


logger = get_logger("diary.audio_service")


class AudioService:
    """负责语音包、音频生成和音频资源查询。"""

    def __init__(
        self,
        diary_service: DiaryService,
        audio_repository: AudioRepository,
        provider: TTSProvider,
        audio_root: Path,
        default_voice_name: str,
        generation_timeout_seconds: int = 90,
    ):
        self.diary_service = diary_service
        self.audio_repository = audio_repository
        self.provider = provider
        self.audio_root = Path(audio_root)
        self.default_voice_name = default_voice_name
        self.generation_timeout_seconds = generation_timeout_seconds
        self.audio_root.mkdir(parents=True, exist_ok=True)
        self._ensure_default_voice()

    @staticmethod
    def _hash_voice(voice: Dict[str, Any]) -> str:
        payload = {
            "provider": voice["provider"],
            "language": voice["language"],
            "voice_name": voice["voice_name"],
            "speed": voice["speed"],
            "pitch": voice["pitch"],
        }
        value = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"

    def _ensure_default_voice(self) -> None:
        voice = {
            "id": str(uuid5(NAMESPACE_URL, "diary:voice:default-edge-tts-zh-cn")),
            "name": "普通话女声",
            "provider": "edge_tts",
            "language": "zh-CN",
            "voice_name": self.default_voice_name,
            "speed": 1.0,
            "pitch": 1.0,
            "offline_supported": False,
            "created_at": utc_now(),
        }
        voice["config_hash"] = self._hash_voice(voice)
        self.audio_repository.ensure_voice(voice)

    def list_voices(self) -> List[Dict[str, Any]]:
        return self.audio_repository.list_voices()

    def list_assets(self, diary_id: str) -> List[Dict[str, Any]]:
        self.diary_service.get_diary(diary_id)
        return self.audio_repository.list_assets(diary_id)

    def get_asset(self, asset_id: str) -> Dict[str, Any]:
        asset = self.audio_repository.get_asset(asset_id)
        if not asset or asset["status"] != "ready":
            raise ServiceError("AUDIO_ASSET_NOT_FOUND", "音频资源不存在", 404)
        if not Path(asset["file_path"]).is_file():
            raise ServiceError("AUDIO_FILE_NOT_FOUND", "音频文件不存在", 404)
        return asset

    async def generate(self, diary_id: str, voice_id: Optional[str]) -> Dict[str, Any]:
        diary = self.diary_service.get_diary(diary_id)
        voices = self.audio_repository.list_voices()
        selected_id = voice_id or voices[0]["id"]
        voice = self.audio_repository.get_voice(selected_id)
        if not voice:
            raise ServiceError("VOICE_NOT_FOUND", "语音包不存在", 404)

        ready = self.audio_repository.find_ready(
            diary_id, voice["id"], diary["content_hash"], voice["config_hash"]
        )
        if ready:
            return ready

        self.audio_repository.expire_for_diary(diary_id, diary["content_hash"])
        asset_id = str(uuid4())
        output_dir = self.audio_root / voice["id"]
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{diary_id}_{diary['content_hash'][7:]}_{voice['config_hash'][7:]}.mp3"
        temp_path = output_path.with_suffix(".tmp")
        record = self.audio_repository.create_generating(
            {
                "id": asset_id,
                "diary_id": diary_id,
                "voice_id": voice["id"],
                "content_hash": diary["content_hash"],
                "voice_config_hash": voice["config_hash"],
                "format": "mp3",
                "file_path": str(output_path),
                "created_at": utc_now(),
            }
        )
        try:
            duration_ms = await asyncio.wait_for(
                self.provider.synthesize(diary["content"], temp_path, voice),
                timeout=self.generation_timeout_seconds,
            )
            temp_path.replace(output_path)
            file_hash = self._file_hash(output_path)
            result = self.audio_repository.mark_ready(record["id"], duration_ms, file_hash)
            logger.info("audio_generated", extra={"diary_id": diary_id, "asset_id": record["id"]})
            return result
        except Exception as exc:
            if temp_path.exists():
                temp_path.unlink()
            self.audio_repository.mark_failed(record["id"])
            logger.exception("audio_generation_failed", extra={"diary_id": diary_id})
            raise ServiceError("AUDIO_GENERATION_FAILED", "音频生成失败", 502) from exc

    @staticmethod
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return f"sha256:{digest.hexdigest()}"

