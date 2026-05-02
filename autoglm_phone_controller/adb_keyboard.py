from __future__ import annotations

from pathlib import Path

from .adb import AdbClient
from .runtime import resource_path


ADB_KEYBOARD_PACKAGE = "com.android.adbkeyboard"
ADB_KEYBOARD_IME = "com.android.adbkeyboard/.AdbIME"
DEFAULT_APK_PATH = resource_path("apk", "ADBKeyboard.apk")


def setup_adb_keyboard(device_id: str, apk_path: Path = DEFAULT_APK_PATH) -> dict:
    adb = AdbClient(device_id)
    steps: list[dict] = []

    def record(name: str, ok: bool, message: str) -> None:
        steps.append({"name": name, "ok": ok, "message": message})

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
            return _summary(steps)

    try:
        record("enable_ime", True, adb.enable_ime(ADB_KEYBOARD_IME))
    except Exception as exc:
        record("enable_ime", False, str(exc))

    try:
        record("set_ime", True, adb.set_ime(ADB_KEYBOARD_IME))
    except Exception as exc:
        record("set_ime", False, str(exc))

    try:
        current = adb.current_ime()
        record("check_current_ime", ADB_KEYBOARD_IME in current, current)
    except Exception as exc:
        record("check_current_ime", False, str(exc))

    return _summary(steps)


def _summary(steps: list[dict]) -> dict:
    return {
        "ok": all(step["ok"] for step in steps),
        "steps": steps,
    }
