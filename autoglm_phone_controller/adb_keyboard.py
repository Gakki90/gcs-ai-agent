from __future__ import annotations

import logging
from pathlib import Path

from .adb import AdbClient
from .runtime import resource_path


ADB_KEYBOARD_PACKAGE = "com.android.adbkeyboard"
ADB_KEYBOARD_IME = "com.android.adbkeyboard/.AdbIME"
DEFAULT_APK_PATH = resource_path("apk", "ADBKeyboard.apk")
logger = logging.getLogger(__name__)


def setup_adb_keyboard(device_id: str, apk_path: Path = DEFAULT_APK_PATH) -> dict:
    adb = AdbClient(device_id)
    steps: list[dict] = []
    logger.info("adb keyboard setup start device=%s apk=%s", device_id, apk_path)

    def record(name: str, ok: bool, message: str) -> None:
        steps.append({"name": name, "ok": ok, "message": message})
        log_method = logger.info if ok else logger.error
        log_method("adb keyboard step device=%s step=%s ok=%s message=%s", device_id, name, ok, message)

    try:
        packages = adb.list_packages(ADB_KEYBOARD_PACKAGE)
        installed = ADB_KEYBOARD_PACKAGE in packages
        record("check_installed", True, "已安装" if installed else "未安装")
    except Exception as exc:
        installed = False
        record("check_installed", False, str(exc))

    if not installed:
        try:
            record("install_apk", True, adb.install_apk(apk_path))
        except Exception as exc:
            record("install_apk", False, str(exc))
            summary = _summary(steps)
            logger.error("adb keyboard setup failed device=%s summary=%s", device_id, summary)
            return summary

    try:
        record("enable_ime", True, adb.enable_ime(ADB_KEYBOARD_IME))
    except Exception as exc:
        record("enable_ime", False, str(exc))

    try:
        enabled = adb.enabled_imes()
        record("check_enabled_ime", ADB_KEYBOARD_IME in enabled, enabled)
    except Exception as exc:
        record("check_enabled_ime", False, str(exc))

    summary = _summary(steps)
    if summary["ok"]:
        logger.info("adb keyboard setup done device=%s summary=%s", device_id, summary)
    else:
        logger.error("adb keyboard setup incomplete device=%s summary=%s", device_id, summary)
    return summary


def _summary(steps: list[dict]) -> dict:
    return {
        "ok": all(step["ok"] for step in steps),
        "steps": steps,
    }
