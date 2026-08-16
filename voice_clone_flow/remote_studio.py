from __future__ import annotations

import io
import json
import wave
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from .remote_config import RemoteStudioConfig


class RemoteStudioError(RuntimeError):
    pass


class RemoteStudioAuthError(RemoteStudioError):
    pass


class RemoteStudioConnectionError(RemoteStudioError):
    pass


class RemoteStudioBusyError(RemoteStudioError):
    pass


class RemoteStudioProtocolError(RemoteStudioError):
    pass


class RemoteStudioClient:
    def __init__(self, config: RemoteStudioConfig, opener: Callable = urlopen):
        self.config = config.validate()
        self.opener = opener

    def _request(self, path: str, payload: dict | None = None):
        url = urljoin(self.config.base_url + "/", path.lstrip("/"))
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = Request(
            url,
            data=body,
            method="POST" if body is not None else "GET",
            headers={
                "Accept": "application/json, audio/wav",
                "Authorization": f"Bearer {self.config.token}",
                **({"Content-Type": "application/json"} if body is not None else {}),
            },
        )
        try:
            return self.opener(request, timeout=self.config.timeout_seconds)
        except HTTPError as exc:
            if exc.code == 401 or exc.code == 403:
                raise RemoteStudioAuthError("Studio Token 无效") from exc
            if exc.code == 429:
                raise RemoteStudioBusyError("Studio 当前繁忙") from exc
            raise RemoteStudioProtocolError(f"Studio 返回 HTTP {exc.code}") from exc
        except (OSError, URLError, TimeoutError) as exc:
            raise RemoteStudioConnectionError("无法连接 VoiceClone Studio") from exc

    def health(self) -> dict:
        try:
            with self._request("/api/health") as response:
                value = json.loads(response.read().decode("utf-8"))
        except RemoteStudioError:
            raise
        except (ValueError, TypeError, UnicodeError) as exc:
            raise RemoteStudioProtocolError("Studio 健康检查返回格式无效") from exc
        if not isinstance(value, dict):
            raise RemoteStudioProtocolError("Studio 健康检查返回格式无效")
        return value

    def list_voices(self) -> list[dict]:
        try:
            with self._request("/api/voices") as response:
                value = json.loads(response.read().decode("utf-8"))
        except RemoteStudioError:
            raise
        except (ValueError, TypeError, UnicodeError) as exc:
            raise RemoteStudioProtocolError("Studio 音色列表返回格式无效") from exc
        voices = value.get("voices", value) if isinstance(value, dict) else value
        if not isinstance(voices, list) or not all(isinstance(item, dict) for item in voices):
            raise RemoteStudioProtocolError("Studio 音色列表返回格式无效")
        return voices

    def _json_request(self, path: str, payload: dict | None = None) -> dict:
        try:
            with self._request(path, payload) as response:
                value = json.loads(response.read().decode("utf-8"))
        except RemoteStudioError:
            raise
        except (ValueError, TypeError, UnicodeError) as exc:
            raise RemoteStudioProtocolError("Studio 返回格式无效") from exc
        if not isinstance(value, dict):
            raise RemoteStudioProtocolError("Studio 返回格式无效")
        return value

    def claim_provider_delivery(self) -> dict | None:
        value = self._json_request("/api/provider-deliveries/claim", {})
        delivery = value.get("delivery")
        if delivery is not None and not isinstance(delivery, dict):
            raise RemoteStudioProtocolError("Studio Provider 投递格式无效")
        return delivery

    def report_provider_delivery(
        self,
        task_id: str,
        stage: str,
        message: str = "",
        error: str = "",
    ) -> dict:
        value = self._json_request(
            f"/api/provider-deliveries/{task_id}/report",
            {"stage": stage, "message": message, "error": error},
        )
        delivery = value.get("delivery")
        if not isinstance(delivery, dict):
            raise RemoteStudioProtocolError("Studio Provider 回执格式无效")
        return delivery

    def verify_provider(self, voice_id: str, text_language: str) -> dict:
        language = str(text_language or "中文").strip()
        prompt = "確認です。" if language in {"日文", "ja", "ja-JP"} else "测试。"
        value = self._json_request(
            "/infer_single",
            {
                "dl_url": self.config.base_url,
                "version": "v2Pro",
                "model_name": str(voice_id).strip(),
                "text": prompt,
                "text_lang": language,
                "provider_verification": True,
            },
        )
        audio_url = str(value.get("audio_url", "")).strip()
        expected = urlsplit(self.config.base_url)
        actual = urlsplit(audio_url)
        if (
            actual.scheme != expected.scheme
            or actual.netloc != expected.netloc
            or not actual.path.startswith("/api/audio/")
        ):
            raise RemoteStudioProtocolError("Studio 验收音频地址无效")

        try:
            with self._request(audio_url) as response:
                audio = response.read(2 * 1024 * 1024 + 1)
        except RemoteStudioError:
            raise
        except OSError as exc:
            raise RemoteStudioConnectionError("Studio 验收音频下载失败") from exc
        if len(audio) > 2 * 1024 * 1024:
            raise RemoteStudioProtocolError("Studio 验收音频超过 2 MB")
        if not audio.startswith(b"RIFF") or audio[8:12] != b"WAVE":
            raise RemoteStudioProtocolError("Studio 验收结果不是有效 WAV")
        try:
            with wave.open(io.BytesIO(audio), "rb") as source:
                duration = source.getnframes() / source.getframerate()
        except (wave.Error, EOFError, ZeroDivisionError) as exc:
            raise RemoteStudioProtocolError("Studio 验收 WAV 无法解析") from exc
        if duration > 1.5:
            raise RemoteStudioProtocolError("Studio 验收音频超过 1.5 秒")
        return {"duration_seconds": duration, "size_bytes": len(audio)}

    def synthesize(self, payload: dict, destination: Path) -> Path:
        try:
            with self._request("/api/tts", payload) as response:
                destination = Path(destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("wb") as target:
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        target.write(chunk)
        except RemoteStudioError:
            raise
        except OSError as exc:
            raise RemoteStudioConnectionError("远程音频写入失败") from exc
        if not destination.is_file() or destination.stat().st_size == 0:
            raise RemoteStudioProtocolError("Studio 未返回音频数据")
        return destination
