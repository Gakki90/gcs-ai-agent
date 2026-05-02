from __future__ import annotations

import inspect
import json
import os
import base64
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from .adb import AdbClient
from .config import AppConfig
from .gesture import install_phone_agent_gesture_patch


class AutoGlmError(RuntimeError):
    pass


def _construct(cls: type[Any], **values: Any) -> Any:
    signature = inspect.signature(cls)
    accepted = {
        name
        for name, parameter in signature.parameters.items()
        if parameter.kind in (parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY)
    }
    kwargs = {name: value for name, value in values.items() if name in accepted and value is not None}
    return cls(**kwargs)


def _load_phone_agent_classes() -> tuple[type[Any], type[Any], type[Any] | None]:
    try:
        from phone_agent import PhoneAgent
        from phone_agent.agent import AgentConfig
        from phone_agent.model import ModelConfig

        return PhoneAgent, ModelConfig, AgentConfig
    except ImportError as exc:
        try:
            from phone_agent import ModelConfig, PhoneAgent

            return PhoneAgent, ModelConfig, None
        except ImportError:
            raise AutoGlmError(
                "未安装 Open-AutoGLM 的 phone_agent。请在当前 .venv 已激活的终端里进入 "
                "Open-AutoGLM 源码目录，然后运行: python -m pip install -r requirements.txt && "
                "python -m pip install -e ."
            ) from exc


def _prepare_agent(
    config: AppConfig,
    *,
    max_steps: int,
    system_prompt: str | None = None,
    confirmation_callback: Any | None = None,
    takeover_callback: Any | None = None,
) -> tuple[Any, str]:
    if not config.api_key:
        raise AutoGlmError("缺少 API Key。请设置 BIGMODEL_API_KEY，或通过 --api-key 传入。")

    adb = AdbClient(config.device_id)
    device = adb.select_device()

    os.environ.setdefault("BIGMODEL_API_KEY", config.api_key)
    os.environ.setdefault("ZHIPUAI_API_KEY", config.api_key)
    os.environ.setdefault("PHONE_AGENT_API_KEY", config.api_key)
    os.environ.setdefault("PHONE_AGENT_BASE_URL", config.base_url)
    os.environ.setdefault("PHONE_AGENT_MODEL", config.model)
    os.environ.setdefault("PHONE_AGENT_DEVICE_ID", device.serial)

    PhoneAgent, ModelConfig, AgentConfig = _load_phone_agent_classes()
    install_phone_agent_gesture_patch()

    model_config = _construct(
        ModelConfig,
        api_key=config.api_key,
        key=config.api_key,
        base_url=config.base_url,
        model=config.model,
        model_name=config.model,
        lang="cn",
    )

    agent_config = None
    if AgentConfig is not None:
        agent_config = _construct(
            AgentConfig,
            max_steps=max_steps,
            device_id=device.serial,
            verbose=True,
            lang="cn",
            system_prompt=system_prompt,
        )

    agent = _construct(
        PhoneAgent,
        model_config=model_config,
        agent_config=agent_config,
        confirmation_callback=confirmation_callback,
        takeover_callback=takeover_callback,
    )
    return agent, device.serial


def _summarize_image_url(
    url: str,
    *,
    include_base64: bool,
    image_dir: Path | None = None,
    image_prefix: str = "image",
    relative_to: Path | None = None,
) -> dict[str, Any] | str:
    if not url.startswith("data:image"):
        return url

    header, _, base64_data = url.partition(",")
    summary: dict[str, Any] = {
        "type": "image_url",
        "header": header,
        "base64_length": len(base64_data),
        "base64_prefix": base64_data[:120],
        "base64_suffix": base64_data[-120:] if base64_data else "",
    }
    if image_dir is not None:
        image_dir.mkdir(parents=True, exist_ok=True)
        ext = "png"
        if "/" in header:
            ext = header.split("/", 1)[1].split(";", 1)[0] or "png"
        image_path = image_dir / f"{image_prefix}.{ext}"
        image_path.write_bytes(base64.b64decode(base64_data))
        if relative_to is not None:
            summary["image_path"] = os.path.relpath(image_path, start=relative_to)
        else:
            summary["image_path"] = str(image_path)
    if include_base64:
        summary["base64"] = base64_data
    return summary


def _sanitize_messages(
    messages: list[dict[str, Any]],
    *,
    include_base64: bool,
    image_dir: Path | None = None,
    step_index: int = 0,
    relative_to: Path | None = None,
) -> list[dict[str, Any]]:
    sanitized = json.loads(json.dumps(messages, ensure_ascii=False))
    image_index = 0
    for message in sanitized:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            image_index += 1
            image_prefix = f"step-{step_index:03d}-image-{image_index:02d}"
            image_url = item.get("image_url")
            if isinstance(image_url, dict) and isinstance(image_url.get("url"), str):
                image_url["url"] = _summarize_image_url(
                    image_url["url"],
                    include_base64=include_base64,
                    image_dir=image_dir,
                    image_prefix=image_prefix,
                    relative_to=relative_to,
                )
            elif isinstance(image_url, str):
                item["image_url"] = _summarize_image_url(
                    image_url,
                    include_base64=include_base64,
                    image_dir=image_dir,
                    image_prefix=image_prefix,
                    relative_to=relative_to,
                )
    return sanitized


def run_task(
    task: str,
    config: AppConfig,
    *,
    preflight: bool = True,
    max_steps: int = 100,
    trace_txt: Path | None = None,
    trace_include_base64: bool = False,
) -> Any:
    adb = AdbClient(config.device_id)
    device = adb.select_device()

    if preflight:
        adb.wake()

    agent, _ = _prepare_agent(config, max_steps=max_steps)

    if trace_txt is not None:
        return run_task_with_trace(
            task,
            agent,
            config,
            device.serial,
            trace_txt,
            max_steps=max_steps,
            include_base64=trace_include_base64,
        )

    if hasattr(agent, "run"):
        return agent.run(task)
    if hasattr(agent, "execute"):
        return agent.execute(task)
    raise AutoGlmError("phone_agent.PhoneAgent 没有可识别的 run/execute 方法，请检查 phone-agent 版本。")


def run_task_with_trace(
    task: str,
    agent: Any,
    config: AppConfig,
    device_id: str,
    trace_txt: Path,
    *,
    max_steps: int,
    include_base64: bool = False,
) -> str:
    if not hasattr(agent, "step"):
        raise AutoGlmError("当前 phone_agent.PhoneAgent 不支持 step()，无法记录逐步 trace。")

    trace_txt.parent.mkdir(parents=True, exist_ok=True)
    image_dir = trace_txt.parent / f"{trace_txt.stem}_images"
    original_request = agent.model_client.request
    latest_response: dict[str, Any] = {}
    latest_messages: dict[str, list[dict[str, Any]]] = {}

    def traced_request(messages: list[dict[str, Any]]) -> Any:
        latest_messages["value"] = deepcopy(messages)
        response = original_request(messages)
        latest_response["value"] = response
        return response

    agent.model_client.request = traced_request

    with trace_txt.open("w", encoding="utf-8") as file:
        file.write("AutoGLM Phone Trace\n")
        file.write(f"created_at: {datetime.now().isoformat(timespec='seconds')}\n")
        file.write(f"task: {task}\n")
        file.write(f"model: {config.model}\n")
        file.write(f"base_url: {config.base_url}\n")
        file.write(f"device_id: {device_id}\n")
        file.write(f"max_steps: {max_steps}\n")
        file.write(f"include_full_base64: {include_base64}\n")
        file.write("=" * 80 + "\n\n")

        final_message = "Max steps reached"
        for step_index in range(1, max_steps + 1):
            latest_response.clear()
            latest_messages.clear()
            result = agent.step(task if step_index == 1 else None)
            response = latest_response.get("value")
            messages = latest_messages.get("value", [])

            file.write(f"STEP {step_index}\n")
            file.write("-" * 80 + "\n")
            file.write(f"success: {result.success}\n")
            file.write(f"finished: {result.finished}\n")
            file.write(f"message: {result.message or ''}\n\n")

            file.write("[REQUEST MESSAGES]\n")
            file.write(
                json.dumps(
                    _sanitize_messages(
                        messages,
                        include_base64=include_base64,
                        image_dir=image_dir,
                        step_index=step_index,
                        relative_to=trace_txt.parent,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            file.write("\n\n")

            file.write("[MODEL THINKING]\n")
            file.write((getattr(response, "thinking", None) or result.thinking or "").strip())
            file.write("\n\n")

            file.write("[MODEL ACTION RAW]\n")
            file.write((getattr(response, "action", None) or "").strip())
            file.write("\n\n")

            file.write("[PARSED ACTION]\n")
            file.write(str(result.action))
            file.write("\n\n")

            file.write("[MODEL RAW CONTENT]\n")
            file.write((getattr(response, "raw_content", None) or "").strip())
            file.write("\n\n")

            if response is not None:
                file.write("[MODEL TIMING]\n")
                file.write(f"time_to_first_token: {getattr(response, 'time_to_first_token', None)}\n")
                file.write(f"time_to_thinking_end: {getattr(response, 'time_to_thinking_end', None)}\n")
                file.write(f"total_time: {getattr(response, 'total_time', None)}\n\n")

            file.write("=" * 80 + "\n\n")
            file.flush()

            if result.finished:
                final_message = result.message or "Task completed"
                break

    return f"{final_message}\nTrace saved to: {trace_txt}"
