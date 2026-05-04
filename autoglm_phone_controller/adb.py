from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
import re

from .runtime import adb_executable


class AdbError(RuntimeError):
    pass


@dataclass(frozen=True)
class AdbDevice:
    serial: str
    state: str
    description: str = ""


def _run_adb(args: list[str], *, serial: str | None = None, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    command = [adb_executable()]
    if serial:
        command += ["-s", serial]
    command += args
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise AdbError("未找到 adb，请先安装 Android Platform Tools，并确保 adb 在 PATH 中。") from exc
    except subprocess.TimeoutExpired as exc:
        raise AdbError(f"adb 命令超时: {' '.join(command)}") from exc


def _restart_adb_server() -> None:
    adb = adb_executable()
    for args in (["kill-server"], ["start-server"]):
        try:
            subprocess.run([adb, *args], capture_output=True, text=True, timeout=10, check=False)
            time.sleep(0.4)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return


def _run_adb_with_server_retry(
    args: list[str], *, serial: str | None = None, timeout: int = 20
) -> subprocess.CompletedProcess[str]:
    last_error: AdbError | None = None
    for attempt in range(3):
        try:
            result = _run_adb(args, serial=serial, timeout=timeout)
        except AdbError as exc:
            last_error = exc
            if "超时" not in str(exc) or attempt == 2:
                raise
            _restart_adb_server()
            continue

        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        if result.returncode != 0 and "failed to check server version" in output.lower() and attempt < 2:
            _restart_adb_server()
            continue
        return result
    if last_error:
        raise last_error
    return _run_adb(args, serial=serial, timeout=timeout)


def parse_adb_devices(output: str) -> list[AdbDevice]:
    devices: list[AdbDevice] = []
    for raw_line in output.splitlines()[1:]:
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) >= 2:
            devices.append(
                AdbDevice(
                    serial=parts[0],
                    state=parts[1],
                    description=parts[2] if len(parts) == 3 else "",
                )
            )
    return devices


class AdbClient:
    def __init__(self, serial: str | None = None):
        self.serial = serial

    def devices(self) -> list[AdbDevice]:
        result = _run_adb_with_server_retry(["devices", "-l"], timeout=12)
        if result.returncode != 0:
            raise AdbError(result.stderr.strip() or "adb devices 执行失败。")
        return parse_adb_devices(result.stdout)

    def select_device(self) -> AdbDevice:
        devices = self.devices()
        if self.serial:
            for device in devices:
                if device.serial == self.serial:
                    if device.state != "device":
                        raise AdbError(f"设备 {self.serial} 当前状态是 {device.state}，不是 device。")
                    return device
            raise AdbError(f"没有找到指定设备: {self.serial}")

        ready = [device for device in devices if device.state == "device"]
        if not ready:
            raise AdbError("没有可用 Android 设备。请连接 USB、打开 USB 调试，并在手机上允许调试授权。")
        if len(ready) > 1:
            serials = ", ".join(device.serial for device in ready)
            raise AdbError(f"检测到多台设备，请通过 --device-id 指定其中一台: {serials}")
        return ready[0]

    def shell(self, command: str, *, timeout: int = 20) -> str:
        result = _run_adb(["shell", command], serial=self.serial, timeout=timeout)
        if result.returncode != 0:
            raise AdbError(result.stderr.strip() or f"adb shell 失败: {command}")
        return result.stdout.strip()

    def wake(self) -> None:
        self.shell("input keyevent KEYCODE_WAKEUP")

    def home(self) -> None:
        self.shell("input keyevent KEYCODE_HOME")

    def tap(self, x: int, y: int) -> None:
        self.shell(f"input tap {x} {y}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self.shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    def screen_size(self) -> tuple[int, int]:
        output = self.shell("wm size")
        match = re.search(r"Physical size:\s*(\d+)x(\d+)", output)
        if not match:
            match = re.search(r"Override size:\s*(\d+)x(\d+)", output)
        if not match:
            raise AdbError(f"无法解析屏幕尺寸: {output}")
        return int(match.group(1)), int(match.group(2))

    def launch_package(self, package_name: str) -> None:
        self.shell(f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1", timeout=30)

    def type_text(self, text: str) -> None:
        escaped = text.replace("\\", "\\\\").replace(" ", "%s").replace('"', '\\"')
        self.shell(f'input text "{escaped}"')

    def install_apk(self, apk_path: Path) -> str:
        if not apk_path.exists():
            raise AdbError(f"APK 不存在: {apk_path}")
        result = _run_adb(["install", "-r", str(apk_path)], serial=self.serial, timeout=60)
        output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        if result.returncode != 0:
            raise AdbError(output or "APK 安装失败。")
        return output or "Success"

    def list_packages(self, package_name: str) -> str:
        return self.shell(f"pm list packages {package_name}", timeout=10)

    def enable_ime(self, ime_id: str) -> str:
        return self.shell(f"ime enable {ime_id}", timeout=10)

    def set_ime(self, ime_id: str) -> str:
        return self.shell(f"ime set {ime_id}", timeout=10)

    def current_ime(self) -> str:
        return self.shell("settings get secure default_input_method", timeout=10)

    def screenshot(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [adb_executable()]
        if self.serial:
            command += ["-s", self.serial]
        command += ["exec-out", "screencap", "-p"]
        try:
            result = subprocess.run(command, capture_output=True, timeout=30, check=False)
        except FileNotFoundError as exc:
            raise AdbError("未找到 adb，请先安装 Android Platform Tools，并确保 adb 在 PATH 中。") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError("截图命令超时。") from exc
        if result.returncode != 0:
            raise AdbError(result.stderr.decode(errors="replace").strip() or "截图失败。")
        output_path.write_bytes(result.stdout)
        return output_path
