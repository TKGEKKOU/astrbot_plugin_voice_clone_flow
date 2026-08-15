from __future__ import annotations

import json
import os
import shutil
import string
import subprocess
import threading
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .platform_runtime import PlatformProfile, detect_platform_profile
from .linux_tools import LinuxToolInstaller, ffmpeg_download_url

FFMPEG_WINDOWS_URLS = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip",
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
)
FFMPEG_URL = FFMPEG_WINDOWS_URLS[0]
# 国内可访问的 GitHub Releases 加速镜像。作为测速候选自动参与排序，
# 实测吞吐落后或不可达的源会被自然淘汰，不影响官方源正常使用。
GITHUB_MIRROR_PREFIXES = (
    "https://ghfast.top/",
    "https://gh-proxy.com/",
)
FFMPEG_WINDOWS_MIRROR_URLS = tuple(
    prefix + FFMPEG_URL for prefix in GITHUB_MIRROR_PREFIXES
)
FFMPEG_DOWNLOAD_TIMEOUT_SECONDS = 60
# 测速参数：并行探测每个候选源下载前 512KB 的实测吞吐，超时 10 秒。
FFMPEG_PROBE_BYTES = 512 * 1024
FFMPEG_PROBE_TIMEOUT_SECONDS = 10
FFMPEG_PROBE_CACHE_TTL_SECONDS = 300


class FFmpegResourceManager:
    def __init__(
        self,
        data_dir: Path,
        configured_path: str = "",
        download_url: str | None = None,
        which=shutil.which,
        common_paths: tuple[Path, ...] | None = None,
        platform_profile: PlatformProfile | None = None,
    ) -> None:
        self.platform_profile = platform_profile or detect_platform_profile(which=which)
        self._profile_injected = platform_profile is not None
        self.root = Path(data_dir) / "runtime" / "ffmpeg"
        suffix = ".exe" if self.platform_profile.system == "windows" else ""
        self.managed_ffmpeg = self.root / f"ffmpeg{suffix}"
        self.managed_ffprobe = self.root / f"ffprobe{suffix}"
        self.configured_path = configured_path
        self.download_url = download_url or FFMPEG_URL
        self._custom_download_url = bool(download_url)
        self.which = which
        self.part_file = self.root.parent / "ffmpeg.zip.part"
        self.part_meta_file = self.root.parent / "ffmpeg.zip.part.meta"
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        program_files = Path(os.environ.get("ProgramFiles", ""))
        self.common_paths = common_paths or (
            local / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
            program_files / "ffmpeg" / "bin" / "ffmpeg.exe",
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
        )
        self.installing = False
        self.probing = False
        self.error = ""
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self._lock = threading.Lock()
        self._speed_cache: dict[str, tuple[float, float]] = {}

    def resolve(self) -> Path | None:
        if self.configured_path and Path(self.configured_path).is_file():
            return Path(self.configured_path).resolve()
        if self.managed_ffmpeg.is_file():
            return self.managed_ffmpeg.resolve()
        found = self.which("ffmpeg")
        if found:
            return Path(found)
        if self.platform_profile.system == "windows":
            found = self._where_windows_ffmpeg()
            if found:
                return found
        common = next(
            (path.resolve() for path in self.common_paths if path.is_file()), None
        )
        return common or (
            self._detect_portable_windows_ffmpeg()
            if self.platform_profile.system == "windows"
            else None
        )

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

    def _where_windows_ffmpeg(self) -> Path | None:
        """Resolve FFmpeg from the Windows system search path as seen by cmd.exe."""
        try:
            result = subprocess.run(
                ["where.exe", "ffmpeg.exe"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        for line in result.stdout.splitlines():
            candidate = Path(line.strip().strip('"'))
            if candidate.is_file():
                return candidate.resolve()
        return None

    def status(self) -> dict[str, object]:
        path = self.resolve()
        source = "missing"
        if path:
            source = (
                "configured"
                if self.configured_path and Path(self.configured_path).is_file()
                else "managed"
                if self.managed_ffmpeg.is_file()
                and path == self.managed_ffmpeg.resolve()
                else "system"
            )
        display_path = path or (
            self.managed_ffmpeg
            if self.platform_profile.system == "windows"
            else "ffmpeg"
        )
        downloaded = self.downloaded_bytes
        total = self.total_bytes
        if (
            self.platform_profile.system == "windows"
            and self.part_file.is_file()
            and not self.installing
        ):
            downloaded = max(downloaded, self.part_file.stat().st_size)
            meta = self._read_part_meta()
            if meta and meta.get("total"):
                total = max(total, int(meta["total"]))
        return {
            "ready": bool(path),
            "installing": self.installing,
            "probing": self.probing,
            "error": self.error,
            "platform": self.platform_profile.system,
            "can_install": self.platform_profile.can_download_managed_ffmpeg,
            "install_hint": self.platform_profile.install_hints.get("ffmpeg", ""),
            "resolved_path": str(display_path),
            "managed_path": str(self.managed_ffmpeg),
            "manual_download_urls": [
                {
                    "name": "BtbN FFmpeg（官方主源）",
                    "url": FFMPEG_WINDOWS_URLS[0],
                },
                {
                    "name": "BtbN 国内加速（ghfast.top 镜像）",
                    "url": FFMPEG_WINDOWS_MIRROR_URLS[0],
                },
                {
                    "name": "BtbN 国内加速（gh-proxy.com 镜像）",
                    "url": FFMPEG_WINDOWS_MIRROR_URLS[1],
                },
                {
                    "name": "Gyan FFmpeg（官方备用源）",
                    "url": FFMPEG_WINDOWS_URLS[1],
                },
            ] if self.platform_profile.system == "windows" else [],
            "source": source,
            "downloaded_bytes": downloaded,
            "total_bytes": total,
            "progress_percent": round(downloaded * 100 / total)
            if total
            else 0,
        }

    def start_install(self) -> bool:
        if not self._profile_injected:
            self.platform_profile = detect_platform_profile(which=self.which)
        if not self.platform_profile.can_download_managed_ffmpeg:
            raise RuntimeError(
                f"当前系统或架构不支持自动下载 FFmpeg："
                f"{self.platform_profile.system}/{self.platform_profile.architecture}"
            )
        if self.platform_profile.system == "linux":
            if self.resolve():
                return False
        with self._lock:
            if self.installing:
                return False
            self.installing, self.error = True, ""
        threading.Thread(
            target=self._install, daemon=True, name="voice-ffmpeg-install"
        ).start()
        return True

    def _install(self) -> None:
        if self.platform_profile.system == "linux":
            self._install_linux()
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            try:
                self._download_loop()
            except Exception as exc:
                # 下载中断：保留断点文件，下次安装继续续传
                self.error = str(exc)
                return
            try:
                self._extract_windows()
            except Exception as exc:
                # 压缩包损坏（例如断点续传遇到上游更新文件），清除断点后全量重下
                self.part_file.unlink(missing_ok=True)
                self.part_meta_file.unlink(missing_ok=True)
                self.error = f"下载包损坏，已清除断点缓存：{exc}"
                return
            self.part_file.unlink(missing_ok=True)
            self.part_meta_file.unlink(missing_ok=True)
        finally:
            self.installing = False

    def _download_loop(self) -> None:
        """并行测速后按实测吞吐排序尝试各下载源，第一个成功的源胜出。

        用户显式配置的下载地址始终排在最前，不参与测速降级；
        其余候选（官方源与国内加速镜像）按实测速度自动排序。
        """
        defaults = tuple(
            dict.fromkeys((*FFMPEG_WINDOWS_URLS, *FFMPEG_WINDOWS_MIRROR_URLS))
        )
        configured = self.download_url if self._custom_download_url else ""
        ordered_defaults = self._rank_sources(defaults)
        if configured:
            ordered = [configured, *[u for u in ordered_defaults if u != configured]]
        else:
            ordered = ordered_defaults
        last_error: Exception | None = None
        for index, source in enumerate(ordered, start=1):
            try:
                self._download_windows(source)
                last_error = None
                self.error = ""
                break
            except (TimeoutError, OSError, urllib.error.HTTPError) as exc:
                last_error = exc
                if index < len(ordered):
                    self.error = f"FFmpeg 下载源 {index} 无响应，正在切换备用源"
        if last_error is not None:
            raise RuntimeError(f"所有 FFmpeg 下载源均不可用：{last_error}") from last_error

    def _rank_sources(self, urls: tuple[str, ...]) -> list[str]:
        """并行探测各候选源的实测下载吞吐，按速度从快到慢排序。"""
        if len(urls) <= 1:
            return list(urls)
        self.probing = True
        try:
            with ThreadPoolExecutor(max_workers=min(len(urls), 6)) as pool:
                futures = {pool.submit(self._probe_speed, url): url for url in urls}
                results: list[tuple[float, str]] = []
                for future, url in futures.items():
                    try:
                        speed = future.result(timeout=FFMPEG_PROBE_TIMEOUT_SECONDS + 5)
                    except Exception:
                        speed = 0.0
                    results.append((speed, url))
        finally:
            self.probing = False
        results.sort(key=lambda item: item[0], reverse=True)
        return [url for _speed, url in results]

    def _probe_speed(self, url: str) -> float:
        """测量单个候选源下载前 512KB 的实测吞吐（bytes/sec），带进程内缓存。"""
        now = time.monotonic()
        cached = self._speed_cache.get(url)
        if cached and now - cached[1] < FFMPEG_PROBE_CACHE_TTL_SECONDS:
            return cached[0]
        speed = 0.0
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "VoiceCloneFlow/0.2",
                    "Accept": "*/*",
                    "Range": f"bytes=0-{FFMPEG_PROBE_BYTES - 1}",
                },
            )
            started = time.monotonic()
            received = 0
            with urllib.request.urlopen(
                request, timeout=FFMPEG_PROBE_TIMEOUT_SECONDS
            ) as response:
                while received < FFMPEG_PROBE_BYTES:
                    block = response.read(64 * 1024)
                    if not block:
                        break
                    received += len(block)
            elapsed = time.monotonic() - started
            if received and elapsed > 0:
                speed = received / elapsed
        except Exception:
            speed = 0.0
        self._speed_cache[url] = (speed, time.monotonic())
        return speed

    def _download_windows(self, url: str) -> None:
        """单源下载，支持基于 Range 的断点续传。

        断点仅在源地址一致时复用（不同源内容不同，不得混用）。
        ETag/Last-Modified 与断点大小记录在 meta 文件中，用于识别上游更新。
        """
        prior = self._read_part_meta()
        existing = self.part_file.stat().st_size if self.part_file.is_file() else 0
        resumable = bool(existing) and prior is not None and prior.get("url") == url
        headers = {"User-Agent": "VoiceCloneFlow/0.2", "Accept": "*/*"}
        if resumable:
            headers["Range"] = f"bytes={existing}-"
            if prior.get("etag"):
                # 上游文件更新（如 BtbN master 滚动构建）时，服务器返回 200 全量，
                # 避免续传产生新旧混合的损坏文件。
                headers["If-Range"] = prior["etag"]
        request = urllib.request.Request(url, headers=headers)
        self.part_file.parent.mkdir(parents=True, exist_ok=True)
        etag = ""
        try:
            with urllib.request.urlopen(
                request, timeout=FFMPEG_DOWNLOAD_TIMEOUT_SECONDS
            ) as response:
                status = getattr(response, "status", 200)
                etag = (
                    response.headers.get("ETag")
                    or response.headers.get("Last-Modified")
                    or ""
                )
                if status == 206 and resumable:
                    total = existing + int(response.headers.get("Content-Length", 0))
                    mode = "ab"
                else:
                    # 服务器不支持 Range 或断点已失效：从头下载
                    existing = 0
                    total = int(response.headers.get("Content-Length", 0))
                    mode = "wb"
                self.total_bytes = total
                self.downloaded_bytes = existing
                with self.part_file.open(mode) as target:
                    while block := response.read(1024 * 1024):
                        target.write(block)
                        self.downloaded_bytes += len(block)
        except urllib.error.HTTPError as exc:
            if exc.code == 416 and existing:
                # 断点超出资源范围：服务器端文件已变化，清除断点后全量重下
                self.part_file.unlink(missing_ok=True)
                self.part_meta_file.unlink(missing_ok=True)
                return self._download_windows(url)
            raise
        if etag:
            self._write_part_meta(url, etag, self.downloaded_bytes)

    def _extract_windows(self) -> None:
        with zipfile.ZipFile(self.part_file) as package:
            for wanted, target in (
                ("ffmpeg.exe", self.managed_ffmpeg),
                ("ffprobe.exe", self.managed_ffprobe),
            ):
                member = next(
                    (
                        n
                        for n in package.namelist()
                        if n.lower().endswith("/bin/" + wanted)
                    ),
                    None,
                )
                if not member:
                    raise RuntimeError(f"压缩包中缺少 {wanted}")
                with package.open(member) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)

    def _read_part_meta(self) -> dict | None:
        try:
            if not self.part_meta_file.is_file():
                return None
            data = json.loads(
                self.part_meta_file.read_text(encoding="utf-8")
            )
            return data if isinstance(data, dict) else None
        except (OSError, ValueError):
            return None

    def _write_part_meta(self, url: str, etag: str, total: int) -> None:
        try:
            self.part_meta_file.write_text(
                json.dumps({"url": url, "etag": etag, "total": total}),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _install_linux(self) -> None:
        archive = self.root.parent / "ffmpeg-linux.tar.xz"
        try:
            installer = LinuxToolInstaller(self.root)
            installer.download(
                ffmpeg_download_url(self.platform_profile.architecture),
                archive,
                self._update_download_progress,
            )
            installer.install_ffmpeg_archive(archive)
        except Exception as exc:
            self.error = str(exc)
        finally:
            archive.unlink(missing_ok=True)
            self.installing = False

    def _update_download_progress(self, downloaded: int, total: int) -> None:
        self.downloaded_bytes = downloaded
        self.total_bytes = total

    def delete_managed(self) -> bool:
        removed = False
        for path in (self.managed_ffmpeg, self.managed_ffprobe):
            if path.is_file():
                path.unlink()
                removed = True
        return removed
