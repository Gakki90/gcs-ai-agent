from __future__ import annotations

from pydantic import BaseModel, Field


class DeviceDto(BaseModel):
    serial: str
    state: str
    description: str = ""


class StartSessionRequest(BaseModel):
    task: str = Field(min_length=1)
    device_id: str
    max_steps: int = 30


class StepRequest(BaseModel):
    hint: str | None = None


class RunRequest(BaseModel):
    hint: str | None = None


class ReplayRequest(BaseModel):
    target_device_ids: list[str] = Field(default_factory=list)
    max_steps: int | None = None
    device_gap_seconds: float = 30.0


class RecordedStepDto(BaseModel):
    index: int
    success: bool
    finished: bool
    action: dict | None = None
    action_name: str | None = None
    image_url: str | None = None
    point_norm: list[int] | None = None
    thinking: str = ""
    message: str | None = None


class SessionDto(BaseModel):
    id: str
    task: str
    platform: str
    source_device_id: str
    status: str
    max_steps: int
    steps: list[RecordedStepDto]
    messages: list[dict]
    workflow_prompt: str | None = None
    summary: str | None = None


class ReplayResultDto(BaseModel):
    device_id: str
    ok: bool
    message: str


class ReplayResponse(BaseModel):
    session_id: str
    results: list[ReplayResultDto]
