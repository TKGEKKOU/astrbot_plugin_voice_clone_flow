from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable


class LinuxPythonEnvironment:
    def __init__(
        self,
        install_dir: Path,
        *,
        current_python: str | None = None,
        uv_path: str | None = None,
        runner: Callable = subprocess.run,
    ) -> None:
        self.install_dir = Path(install_dir)
        self.venv_dir = self.install_dir / ".venv"
        self.python_path = self.venv_dir / "bin" / "python"
        self.current_python = current_python or sys.executable
        self.uv_path = uv_path if uv_path is not None else shutil.which("uv")
        self.runner = runner

    def ensure(self) -> Path:
        if self.python_path.is_file():
            return self.python_path
        self.install_dir.mkdir(parents=True, exist_ok=True)
        command = [self.current_python, "-m", "venv", str(self.venv_dir)]
        try:
            self.runner(command, check=True, capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as first_error:
            if not self.uv_path:
                raise RuntimeError(
                    "无法创建 GPT-SoVITS Python 环境。请安装 python3-venv 或 uv 后重试。"
                ) from first_error
            self.runner(
                [self.uv_path, "venv", "--python", "3.11", str(self.venv_dir)],
                check=True,
                capture_output=True,
                text=True,
            )
        if not self.python_path.is_file():
            raise RuntimeError(f"Python 环境创建完成但未找到：{self.python_path}")
        return self.python_path

    def install_requirements(self, requirements: Path) -> None:
        python = self.ensure()
        if not requirements.is_file():
            raise RuntimeError(f"GPT-SoVITS 源码缺少依赖文件：{requirements}")
        self.runner(
            [str(python), "-m", "pip", "install", "-r", str(requirements)],
            cwd=str(self.install_dir),
            check=True,
        )
