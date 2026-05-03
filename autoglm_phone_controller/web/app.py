from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import time

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from autoglm_phone_controller.adb import AdbClient, AdbError
from autoglm_phone_controller.adb_keyboard import setup_adb_keyboard
from autoglm_phone_controller.runtime import configure_packaged_environment, resource_path
from autoglm_phone_controller.web.models import (
    DeviceDto,
    ReplayRequest,
    ReplayResponse,
    RunRequest,
    StartSessionRequest,
    StepRequest,
)
from autoglm_phone_controller.web.session_store import STATIC_DIR, replay_session, store


app = FastAPI(title="AutoGLM Phone Cluster Console")
configure_packaged_environment()

LOG_DIR = Path(os.getenv("AUTOGLM_LOG_DIR") or "logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "backend-app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

frontend_assets = resource_path("frontend", "dist", "assets")
if frontend_assets.exists():
    app.mount("/assets", StaticFiles(directory=frontend_assets), name="assets")


def _error_detail(exc: Exception) -> str:
    message = str(exc) or exc.__class__.__name__
    return f"{exc.__class__.__name__}: {message}"


def _raise_logged_500(context: str, exc: Exception) -> None:
    logger.exception("%s failed", context)
    raise HTTPException(status_code=500, detail=_error_detail(exc)) from exc


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error during %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": _error_detail(exc)})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/devices", response_model=list[DeviceDto])
def list_devices() -> list[DeviceDto]:
    try:
        return [DeviceDto(serial=d.serial, state=d.state, description=d.description) for d in AdbClient().devices()]
    except AdbError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.websocket("/ws/devices")
async def watch_devices(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            try:
                devices = [
                    DeviceDto(serial=d.serial, state=d.state, description=d.description).model_dump()
                    for d in await asyncio.to_thread(AdbClient().devices)
                ]
                await websocket.send_json({"type": "devices", "devices": devices, "error": None})
            except Exception as exc:
                logger.exception("device websocket poll failed")
                await websocket.send_json({"type": "devices", "devices": [], "error": _error_detail(exc)})
            await asyncio.sleep(1.5)
    except WebSocketDisconnect:
        logger.info("device websocket disconnected")


@app.get("/api/devices/{device_id}/screen")
def device_screen(device_id: str) -> FileResponse:
    path = STATIC_DIR / "screens" / f"{device_id.replace(':', '_')}.png"
    try:
        time.sleep(0.35)
        AdbClient(device_id).screenshot(path)
    except AdbError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FileResponse(
        path,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.post("/api/devices/{device_id}/adb-keyboard/setup")
def setup_device_adb_keyboard(device_id: str) -> dict:
    try:
        return setup_adb_keyboard(device_id)
    except AdbError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/sessions")
def create_session(request: StartSessionRequest):
    try:
        return store.create(request.task, request.device_id, request.max_steps)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _raise_logged_500("create session", exc)


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    try:
        return store.to_dto(store.get(session_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc


@app.post("/api/sessions/{session_id}/step")
def run_step(session_id: str, request: StepRequest):
    try:
        return store.step(session_id, request.hint)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    except Exception as exc:
        _raise_logged_500("run session step", exc)


@app.post("/api/sessions/{session_id}/run")
def run_session(session_id: str, request: RunRequest):
    try:
        return store.run(session_id, request.hint)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    except Exception as exc:
        _raise_logged_500("run session", exc)


@app.post("/api/sessions/{session_id}/finish")
def finish_session(session_id: str):
    try:
        return store.finish(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc


@app.post("/api/sessions/{session_id}/replay", response_model=ReplayResponse)
def replay(session_id: str, request: ReplayRequest) -> ReplayResponse:
    try:
        session = store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    results = replay_session(
        session,
        request.target_device_ids,
        max_steps=request.max_steps,
        device_gap_seconds=request.device_gap_seconds,
    )
    return ReplayResponse(session_id=session_id, results=results)


@app.get("/")
def index() -> FileResponse:
    frontend_index = resource_path("frontend", "dist", "index.html")
    if frontend_index.exists():
        return FileResponse(frontend_index)
    raise HTTPException(status_code=404, detail="frontend has not been built")
