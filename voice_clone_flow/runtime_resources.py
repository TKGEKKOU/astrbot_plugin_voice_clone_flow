from __future__ import annotations

import shutil
import threading
import urllib.request
import zipfile
import os
import string
from pathlib import Path

from .platform_runtime import PlatformProfile, detect_platform_profile

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


class FFmpegResourceManager:
    def __init__(self, data_dir: Path, configured_path: str = "", download_url: str = FFMPEG_URL,
                 which=shutil.which, common_paths: tuple[Path, ...] | None = None,
                 platform_profile: PlatformProfile | None = None) -> None:
        self.platform_profile = platform_profile or detect_platform_profile(which=which)
        self._profile_injected = platform_profile is not None
        self.root = Path(data_dir) / "runtime" / "ffmpeg"
        self.managed_ffmpeg = self.root / "ffmpeg.exe"
        self.managed_ffprobe = self.root / "ffprobe.exe"
        self.configured_path = configured_path
        self.download_url = download_url
        self.which = which
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        program_files = Path(os.environ.get("ProgramFiles", ""))
        self.common_paths = common_paths or (
            local / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
            program_files / "ffmpeg" / "bin" / "ffmpeg.exe",
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
        )
        self.installing = False
        self.error = ""
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self._lock = threading.Lock()

    def resolve(self) -> Path | None:
        if self.configured_path and Path(self.configured_path).is_file():
            return Path(self.configured_path).resolve()
        if self.platform_profile.system == "windows" and self.managed_ffmpeg.is_file():
            return self.managed_ffmpeg.resolve()
        found = self.which("ffmpeg")
        if found:
            return Path(found)
        common = next((path.resolve() for path in self.common_paths if path.is_file()), None)
        return common or (self._detect_portable_windows_ffmpeg() if self.platform_profile.system == "windows" else None)

    def _detect_portable_windows_ffmpeg(self) -> Path | None:
        patterns = (
            "ffmpeg/bin/ffmpeg.exe",
            "tools/ffmpeg/bin/ffmpeg.exe",
        )
        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:/")
            if not drive.exists():
                continue
            for pattern in patterns:
                candidate = drive / pattern
                if candidate.is_file():
                    return candidate.resolve()
        return None

    def status(self) -> dict[str, object]:
        path = self.resolve()
        source = "missing"
        if path:
            source = "configured" if self.configured_path and Path(self.configured_path).is_file() else "managed" if self.managed_ffmpeg.is_file() and path == self.managed_ffmpeg.resolve() else "system"
        display_path = path or (self.managed_ffmpeg if self.platform_profile.system == "windows" else "ffmpeg")
        return {"ready": bool(path), "installing": self.installing, "error": self.error,
                "platform": self.platform_profile.system,
                "can_install": self.platform_profile.can_download_managed_ffmpeg,
                "install_hint": self.platform_profile.install_hints.get("ffmpeg", ""),
                "resolved_path": str(display_path), "managed_path": str(self.managed_ffmpeg),
                "source": source, "downloaded_bytes": self.downloaded_bytes, "total_bytes": self.total_bytes,
                "progress_percent": round(self.downloaded_bytes * 100 / self.total_bytes) if self.total_bytes else 0}

    def start_install(self) -> bool:
        if not self._profile_injected:
            self.platform_profile = detect_platform_profile(which=self.which)
        if self.platform_profile.system == "linux":
            if self.resolve():
                return False
            raise RuntimeError(
                "Linux 上由系统管理 FFmpeg，请在服务器执行："
                + self.platform_profile.install_hints.get("ffmpeg", "sudo apt install -y ffmpeg")
            )
        with self._lock:
            if self.installing:
                return False
            self.installing, self.error = True, ""
        threading.Thread(target=self._install, daemon=True, name="voice-ffmpeg-install").start()
        return True

    def _install(self) -> None:
        archive = self.root.parent / "ffmpeg.zip.part"
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(self.download_url, headers={"User-Agent": "VoiceCloneFlow/0.1"})
            with urllib.request.urlopen(request, timeout=180) as response, archive.open("wb") as target:
                self.total_bytes = int(response.headers.get("Content-Length", 0))
                self.downloaded_bytes = 0
                while block := response.read(1024 * 1024):
                    target.write(block)
                    self.downloaded_bytes += len(block)
            with zipfile.ZipFile(archive) as package:
                for wanted, target in (("ffmpeg.exe", self.managed_ffmpeg), ("ffprobe.exe", self.managed_ffprobe)):
                    member = next((n for n in package.namelist() if n.lower().endswith("/bin/" + wanted)), None)
                    if not member:
                        raise RuntimeError(f"压缩包中缺少 {wanted}")
                    with package.open(member) as src, target.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
        except Exception as exc:
            self.error = str(exc)
        finally:
            archive.unlink(missing_ok=True)
            self.installing = False

    def delete_managed(self) -> bool:
        removed = False
        for path in (self.managed_ffmpeg, self.managed_ffprobe):
            if path.is_file():
                path.unlink()
                removed = True
        return removed
