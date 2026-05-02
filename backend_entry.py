from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TextIO

_LOG_STREAMS: list[TextIO] = []


def _default_log_dir() -> Path:
    env_log_dir = os.getenv("AUTOGLM_LOG_DIR")
    if env_log_dir:
        return Path(env_log_dir)
    executable = Path(sys.executable)
    if getattr(sys, "frozen", False):
        return executable.parent / "logs"
    return Path.cwd() / "logs"


def _configure_windows_stdio(*, redirect_to_file: bool) -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    if redirect_to_file:
        log_dir = _default_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_file = (log_dir / "backend-python-stdout.log").open("a", encoding="utf-8", errors="replace")
        stderr_file = (log_dir / "backend-python-stderr.log").open("a", encoding="utf-8", errors="replace")
        _LOG_STREAMS.extend([stdout_file, stderr_file])
        sys.stdout = stdout_file
        sys.stderr = stderr_file
        return

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    check_imports = "--check-imports" in sys.argv
    _configure_windows_stdio(redirect_to_file=not check_imports)

    import uvicorn

    from autoglm_phone_controller.runtime import configure_packaged_environment

    configure_packaged_environment()
    if check_imports:
        from autoglm_phone_controller.runner import _load_phone_agent_classes
        from autoglm_phone_controller.web.app import app

        _load_phone_agent_classes()
        print(f"imports ok: {app.title}")
        raise SystemExit(0)

    uvicorn.run(
        "autoglm_phone_controller.web.app:app",
        host="127.0.0.1",
        port=18081,
        reload=False,
        log_level="info",
    )
