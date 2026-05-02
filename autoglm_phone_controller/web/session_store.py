from __future__ import annotations

import base64
import os
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autoglm_phone_controller.adb import AdbClient
from autoglm_phone_controller.config import AppConfig, load_config
from autoglm_phone_controller.prompting import (
    UNSUPPORTED_MESSAGE,
    build_ecommerce_system_prompt,
    build_user_task_prompt,
    detect_platform,
)
from autoglm_phone_controller.runner import _prepare_agent
from autoglm_phone_controller.web.models import RecordedStepDto, SessionDto
from autoglm_phone_controller.workflow import build_workflow_prompt


RUNTIME_DIR = Path("runtime")
STATIC_DIR = RUNTIME_DIR / "static"
SESSIONS_DIR = RUNTIME_DIR / "sessions"


@dataclass
class AgentSession:
    id: str
    task: str
    platform: str
    source_device_id: str
    max_steps: int
    config: AppConfig
    agent: Any
    status: str = "ready"
    steps: list[RecordedStepDto] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    latest_response: dict[str, Any] = field(default_factory=dict)
    latest_messages: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    pending_hint: str | None = None
    pending_takeover: str | None = None
    workflow_prompt: str | None = None


class SessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, AgentSession] = {}

    def create(self, task: str, device_id: str, max_steps: int) -> SessionDto:
        platform = detect_platform(task)
        if platform is None:
            raise ValueError(UNSUPPORTED_MESSAGE)
        config = load_config(device_id=device_id)
        agent, serial = _prepare_agent(
            config,
            max_steps=max_steps,
            system_prompt=build_ecommerce_system_prompt(),
            confirmation_callback=lambda message: False,
            takeover_callback=lambda message: self._record_takeover(session_id, message),
        )
        session_id = uuid.uuid4().hex[:12]
        session = AgentSession(
            id=session_id,
            task=task,
            platform=platform,
            source_device_id=serial,
            max_steps=max_steps,
            config=config,
            agent=agent,
        )
        self._attach_recorder(session)
        self.sessions[session_id] = session
        session.messages.append({"role": "user", "content": task})
        return self.to_dto(session)

    def get(self, session_id: str) -> AgentSession:
        if session_id not in self.sessions:
            raise KeyError(session_id)
        return self.sessions[session_id]

    def step(self, session_id: str, hint: str | None = None) -> SessionDto:
        session = self.get(session_id)
        if session.status == "finished":
            return self.to_dto(session)
        if len(session.steps) >= session.max_steps:
            session.status = "max_steps"
            session.messages.append({"role": "system", "content": "已达到最大步数。"})
            return self.to_dto(session)

        first_step = len(session.steps) == 0
        step_task = build_user_task_prompt(session.task, session.platform)
        if hint and first_step:
            step_task = f"{step_task}\n\n人工提示/约束: {hint}"
            session.messages.append({"role": "user", "content": hint})
        elif hint:
            session.pending_hint = hint
            session.messages.append({"role": "user", "content": hint})

        step_index = len(session.steps) + 1
        session.status = "running"
        session.latest_response.clear()
        session.latest_messages.clear()
        result = session.agent.step(step_task if step_index == 1 else None)
        response = session.latest_response.get("value")
        request_messages = session.latest_messages.get("value", [])
        image_url = self._save_latest_image(session.id, step_index, request_messages)
        action = result.action
        recorded = RecordedStepDto(
            index=step_index,
            success=result.success,
            finished=result.finished,
            action=action,
            action_name=action.get("action") if isinstance(action, dict) else None,
            image_url=image_url,
            point_norm=self._extract_primary_point(action),
            thinking=getattr(response, "thinking", None) or result.thinking or "",
            message=result.message,
        )
        session.steps.append(recorded)
        session.workflow_prompt = build_workflow_prompt(
            original_task=session.task,
            platform=session.platform,
            steps=session.steps,
        )
        session.messages.append(
            {
                "role": "assistant",
                "content": session.pending_takeover or recorded.thinking or recorded.message or "模型已返回动作。",
                "action": recorded.action,
                "imageUrl": recorded.image_url,
            }
        )
        if session.pending_takeover:
            session.status = "waiting_takeover"
            session.pending_takeover = None
            return self.to_dto(session)
        session.status = "finished" if result.finished else "waiting"
        return self.to_dto(session)

    def finish(self, session_id: str, message: str = "用户提前结束任务。") -> SessionDto:
        session = self.get(session_id)
        session.status = "finished"
        session.messages.append({"role": "system", "content": message})
        session.workflow_prompt = build_workflow_prompt(
            original_task=session.task,
            platform=session.platform,
            steps=session.steps,
        )
        return self.to_dto(session)

    def to_dto(self, session: AgentSession) -> SessionDto:
        return SessionDto(
            id=session.id,
            task=session.task,
            platform=session.platform,
            source_device_id=session.source_device_id,
            status=session.status,
            max_steps=session.max_steps,
            steps=session.steps,
            messages=session.messages,
            workflow_prompt=session.workflow_prompt,
        )

    def _attach_recorder(self, session: AgentSession) -> None:
        original_request = session.agent.model_client.request

        def traced_request(messages: list[dict[str, Any]]) -> Any:
            self._apply_pending_hint(session, messages)
            session.latest_messages["value"] = deepcopy(messages)
            response = original_request(messages)
            session.latest_response["value"] = response
            session.pending_hint = None
            return response

        session.agent.model_client.request = traced_request

    def _record_takeover(self, session_id: str, message: str) -> None:
        session = self.sessions.get(session_id)
        if session is not None:
            session.pending_takeover = f"需要人工接管：{message}"

    def _apply_pending_hint(self, session: AgentSession, messages: list[dict[str, Any]]) -> None:
        if not session.pending_hint or not messages:
            return

        instruction = (
            "【人工强制提示】\n"
            f"{session.pending_hint}\n\n"
            "下一步动作必须优先遵循这条人工提示；如果它与原任务冲突，以人工提示为准。\n\n"
        )
        latest_user = next((message for message in reversed(messages) if message.get("role") == "user"), None)
        if latest_user is None:
            messages.append({"role": "user", "content": instruction})
            return

        content = latest_user.get("content")
        if isinstance(content, str):
            latest_user["content"] = instruction + content
            return
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    item["text"] = instruction + str(item.get("text", ""))
                    return
            content.append({"type": "text", "text": instruction})

    def _save_latest_image(self, session_id: str, step_index: int, messages: list[dict[str, Any]]) -> str | None:
        for message in reversed(messages):
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if not isinstance(item, dict):
                    continue
                image_url = item.get("image_url")
                if isinstance(image_url, dict):
                    url = image_url.get("url")
                else:
                    url = image_url
                if isinstance(url, str) and url.startswith("data:image"):
                    header, _, base64_data = url.partition(",")
                    ext = "png"
                    if "/" in header:
                        ext = header.split("/", 1)[1].split(";", 1)[0] or "png"
                    rel_path = Path("sessions") / session_id / "images" / f"step-{step_index:03d}.{ext}"
                    image_path = STATIC_DIR / rel_path
                    image_path.parent.mkdir(parents=True, exist_ok=True)
                    image_path.write_bytes(base64.b64decode(base64_data))
                    return f"/static/{rel_path.as_posix()}"
        return None

    @staticmethod
    def _extract_primary_point(action: dict | None) -> list[int] | None:
        if not isinstance(action, dict):
            return None
        for key in ("element", "start"):
            point = action.get(key)
            if isinstance(point, list) and len(point) == 2:
                return [int(point[0]), int(point[1])]
        return None


def replay_session(
    session: AgentSession,
    target_device_ids: list[str],
    *,
    max_steps: int | None = None,
    device_gap_seconds: float = 30.0,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    workflow_prompt = session.workflow_prompt or build_workflow_prompt(
        original_task=session.task,
        platform=session.platform,
        steps=session.steps,
    )
    for index, device_id in enumerate(target_device_ids):
        if index > 0 and device_gap_seconds > 0:
            time.sleep(device_gap_seconds)
        try:
            adb = AdbClient(device_id)
            adb.wake()
            adb.home()
            config = load_config(device_id=device_id)
            agent, _ = _prepare_agent(
                config,
                max_steps=max_steps or session.max_steps,
                system_prompt=build_ecommerce_system_prompt(),
                confirmation_callback=lambda message: False,
                takeover_callback=lambda message: None,
            )
            result = agent.run(workflow_prompt)
            results.append({"device_id": device_id, "ok": True, "message": str(result)})
        except Exception as exc:
            results.append({"device_id": device_id, "ok": False, "message": str(exc)})
    return results


store = SessionStore()
