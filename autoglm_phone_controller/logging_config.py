from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def log_dir() -> Path:
    path = Path(os.getenv("AUTOGLM_LOG_DIR") or "logs")
    path.mkdir(parents=True, exist_ok=True)
    return path


def configure_logging() -> Path:
    directory = log_dir()
    formatter = logging.Formatter(LOG_FORMAT)

    app_handler = logging.FileHandler(directory / "app.log", encoding="utf-8")
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(formatter)

    error_handler = logging.FileHandler(directory / "error.log", encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    root.addHandler(app_handler)
    root.addHandler(error_handler)
    root.addHandler(console_handler)

    adb_handler = logging.FileHandler(directory / "adb.log", encoding="utf-8")
    adb_handler.setLevel(logging.DEBUG)
    adb_handler.setFormatter(formatter)
    adb_logger = logging.getLogger("autoglm_phone_controller.adb")
    adb_logger.handlers.clear()
    adb_logger.setLevel(logging.DEBUG)
    adb_logger.addHandler(adb_handler)

    logging.captureWarnings(True)
    logging.getLogger(__name__).info(
        "logging initialized log_dir=%s executable=%s frozen=%s",
        directory,
        sys.executable,
        bool(getattr(sys, "frozen", False)),
    )
    return directory
