from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .adb import AdbClient, AdbError
from .config import load_config
from .runner import AutoGlmError, run_task


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autoglm-phone",
        description="Use Zhipu AutoGLM Phone to control an Android phone connected over USB/ADB.",
    )
    parser.add_argument("task", nargs="?", help="要让手机执行的自然语言任务。")
    parser.add_argument("--api-key", help="智谱 BigModel API Key。也可使用 BIGMODEL_API_KEY 环境变量。")
    parser.add_argument("--base-url", help="智谱接口地址，默认读取 AUTOGLM_BASE_URL。")
    parser.add_argument("--model", help="模型名，默认 autoglm-phone。")
    parser.add_argument("--device-id", help="adb 设备序列号。多设备连接时必须指定。")
    parser.add_argument("--list-devices", action="store_true", help="列出已连接的 adb 设备。")
    parser.add_argument("--preflight", action="store_true", help="只检查配置和设备，不执行模型任务。")
    parser.add_argument("--no-wake", action="store_true", help="执行任务前不主动唤醒手机。")
    parser.add_argument("--max-steps", type=int, default=100, help="Agent 最多执行多少步，默认 100。")
    parser.add_argument("--trace-txt", type=Path, help="把每一步 LLM 返回内容写入指定 txt 文件。")
    parser.add_argument(
        "--trace-include-base64",
        action="store_true",
        help="trace 中写入完整截图 base64；默认只写长度和前后片段。",
    )
    return parser


def _print_devices(device_id: str | None) -> None:
    devices = AdbClient(device_id).devices()
    if not devices:
        print("未发现 adb 设备。")
        return
    for device in devices:
        suffix = f" {device.description}" if device.description else ""
        print(f"{device.serial}\t{device.state}{suffix}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        device_id=args.device_id,
    )

    try:
        if args.list_devices:
            _print_devices(config.device_id)
            return 0

        device = AdbClient(config.device_id).select_device()
        if args.preflight:
            print(f"ADB 设备可用: {device.serial}")
            print(f"模型: {config.model}")
            print(f"接口: {config.base_url}")
            print("API Key: 已配置" if config.api_key else "API Key: 未配置")
            return 0 if config.api_key else 2

        if not args.task:
            parser.error("请提供任务文本，或使用 --preflight / --list-devices。")

        result = run_task(
            args.task,
            config,
            preflight=not args.no_wake,
            max_steps=args.max_steps,
            trace_txt=args.trace_txt,
            trace_include_base64=args.trace_include_base64,
        )
        if result is not None:
            print(result)
        return 0
    except (AdbError, AutoGlmError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
