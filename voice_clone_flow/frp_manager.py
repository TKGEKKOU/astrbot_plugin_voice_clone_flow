from __future__ import annotations

import json
import os
import platform
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path


class FrpManagerError(RuntimeError):
    pass


class FrpManager:
    VERSION = "0.69.1"
    CONTROL_PORT = 7001
    DEFAULT_REMOTE_PORT = 19090
    ROOT = Path("/opt/frp-voiceclone")
    CONFIG = Path("/etc/frp/frps-voiceclone.toml")
    SERVICE = Path("/etc/systemd/system/frps-voiceclone.service")

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.state_path = self.data_dir / "frp" / "server.json"

    def _state(self) -> dict:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {"bind_port": self.CONTROL_PORT, "remote_port": self.DEFAULT_REMOTE_PORT, "token": ""}

    def _run(self, args: list[str], check: bool = True):
        try:
            return subprocess.run(args, capture_output=True, text=True, timeout=30, check=check)
        except (OSError, subprocess.SubprocessError) as exc:
            raise FrpManagerError(str(exc)) from exc

    def _active(self) -> bool:
        if not self.SERVICE.is_file():
            return False
        return self._run(["systemctl", "is-active", "--quiet", "frps-voiceclone"], check=False).returncode == 0

    def _ensure_binary(self) -> None:
        binary = self.ROOT / "frps"
        if binary.is_file():
            return
        machine = platform.machine().lower()
        arch = "amd64" if machine in {"x86_64", "amd64"} else "arm64" if machine in {"aarch64", "arm64"} else ""
        if not arch:
            raise FrpManagerError(f"暂不支持服务器架构：{machine}")
        name = f"frp_{self.VERSION}_linux_{arch}"
        url = f"https://github.com/fatedier/frp/releases/download/v{self.VERSION}/{name}.tar.gz"
        try:
            with tempfile.TemporaryDirectory() as temp:
                archive = Path(temp) / "frp.tar.gz"
                urllib.request.urlretrieve(url, archive)
                with tarfile.open(archive, "r:gz") as source:
                    member = next((item for item in source.getmembers() if item.name == f"{name}/frps" and item.isfile()), None)
                    if member is None:
                        raise FrpManagerError("FRP 下载包中缺少 frps")
                    extracted = source.extractfile(member)
                    if extracted is None:
                        raise FrpManagerError("无法读取 FRP 可执行文件")
                    binary.write_bytes(extracted.read())
            binary.chmod(0o755)
        except FrpManagerError:
            raise
        except (OSError, tarfile.TarError) as exc:
            raise FrpManagerError(f"FRP 下载或安装失败：{exc}") from exc

    def status(self) -> dict:
        state = self._state()
        return {"platform": platform.system().lower(), "supported": os.name != "nt", "configured": self.CONFIG.is_file(), "config_file": str(self.CONFIG), "service_file": str(self.SERVICE), "bind_port": int(state.get("bind_port", self.CONTROL_PORT)), "remote_port": int(state.get("remote_port", self.DEFAULT_REMOTE_PORT)), "service_active": self._active(), "existing_port_preserved": True}

    def prepare(self, token: str, remote_port: int = DEFAULT_REMOTE_PORT) -> dict:
        if os.name == "nt":
            raise FrpManagerError("服务器端 FRP 准备需要 Linux systemd 环境")
        token = str(token or "").strip()
        remote_port = int(remote_port)
        if not token:
            raise FrpManagerError("FRP Token 不能为空")
        if remote_port <= 1024 or remote_port == 7000:
            raise FrpManagerError("映射端口必须大于 1024 且不能使用 7000")
        self.ROOT.mkdir(parents=True, exist_ok=True)
        self._ensure_binary()
        self.CONFIG.parent.mkdir(parents=True, exist_ok=True)
        self.CONFIG.write_text(f'bindPort = {self.CONTROL_PORT}\nauth.method = "token"\nauth.token = "{token}"\n', encoding="utf-8")
        self.SERVICE.write_text("[Unit]\nDescription=VoiceClone FRP Server\nAfter=network-online.target\n\n[Service]\nType=simple\nExecStart=/opt/frp-voiceclone/frps -c /etc/frp/frps-voiceclone.toml\nRestart=on-failure\nRestartSec=3\n\n[Install]\nWantedBy=multi-user.target\n", encoding="utf-8")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps({"bind_port": self.CONTROL_PORT, "remote_port": remote_port, "token": token}, indent=2), encoding="utf-8")
        self._run(["systemctl", "daemon-reload"])
        self._run(["systemctl", "enable", "--now", "frps-voiceclone"])
        return self.status()

    def restart(self) -> dict:
        if not self.CONFIG.is_file():
            raise FrpManagerError("请先完成 FRP 服务端准备")
        self._run(["systemctl", "restart", "frps-voiceclone"])
        return self.status()
