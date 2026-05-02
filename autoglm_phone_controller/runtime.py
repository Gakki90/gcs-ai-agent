from __future__ import annotations

import os
import sys
from pathlib import Path


def app_root() -> Path:
    env_root = os.getenv("AUTOGLM_APP_ROOT")
    if env_root:
        return Path(env_root)
    return Path.cwd()


def resource_path(*parts: str) -> Path:
    root = app_root()
    candidate = root.joinpath(*parts)
    if candidate.exists():
        return candidate
    pyinstaller_root = getattr(sys, "_MEIPASS", None)
    if pyinstaller_root:
        return Path(pyinstaller_root).joinpath(*parts)
    return candidate


def configure_packaged_environment() -> None:
    platform_tools = resource_path("platform-tools")
    if platform_tools.exists():
        os.environ["PATH"] = str(platform_tools) + os.pathsep + os.environ.get("PATH", "")
