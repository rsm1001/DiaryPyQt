"""语音合成服务适配器。"""
from pathlib import Path
from typing import Any, Dict, Protocol


class TTSProvider(Protocol):
    """语音合成服务接口。"""

    async def synthesize(self, text: str, output_path: Path, voice: Dict[str, Any]) -> int:
        """生成音频并返回毫秒时长。"""


class EdgeTTSProvider:
    """使用 Edge TTS 生成 MP3 音频。"""

    async def synthesize(self, text: str, output_path: Path, voice: Dict[str, Any]) -> int:
        try:
            import edge_tts
            from mutagen import File
        except ImportError as exc:
            raise RuntimeError("语音依赖未安装") from exc

        communicate = edge_tts.Communicate(
            text,
            voice=voice["voice_name"],
            rate=self._rate(voice["speed"]),
            pitch=self._pitch(voice["pitch"]),
        )
        await communicate.save(str(output_path))
        audio = File(str(output_path))
        if audio is None or audio.info is None or not audio.info.length:
            raise RuntimeError("无法读取生成音频时长")
        return max(1, int(audio.info.length * 1000))

    @staticmethod
    def _rate(speed: float) -> str:
        percent = round((speed - 1.0) * 100)
        return f"{percent:+d}%"

    @staticmethod
    def _pitch(pitch: float) -> str:
        percent = round((pitch - 1.0) * 50)
        return f"{percent:+d}Hz"
