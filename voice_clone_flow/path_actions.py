from pathlib import Path
import os
import subprocess


def validate_voice_directory(data_dir: Path, voice_id: str) -> Path:
    root = (Path(data_dir) / "voices").resolve()
    if Path(voice_id).name != voice_id:
        raise ValueError("音色标识无效")
    target = (root / voice_id).resolve()
    if root not in target.parents:
        raise ValueError("音色目录越界")
    if not target.is_dir():
        raise FileNotFoundError("音色目录不存在")
    return target


def open_voice_directory(data_dir: Path, voice_id: str) -> Path:
    target = validate_voice_directory(data_dir, voice_id)
    if hasattr(os, "startfile"):
        os.startfile(str(target))
    else:
        subprocess.Popen(["explorer", str(target)])
    return target


def ensure_voices_root(data_dir: Path) -> Path:
    root = (Path(data_dir) / "voices").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def open_voices_root(data_dir: Path) -> Path:
    target = ensure_voices_root(data_dir)
    if hasattr(os, "startfile"):
        os.startfile(str(target))
    else:
        subprocess.Popen(["explorer", str(target)])
    return target
