from __future__ import annotations

import asyncio
import logging
import time

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from autoglm_phone_controller.adb import AdbClient, AdbError
from autoglm_phone_controller.adb_keyboard import setup_adb_keyboard
from autoglm_phone_controller.logging_config import configure_logging
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
LOG_DIR = configure_logging()
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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = time.monotonic()
    logger.info("http request start method=%s path=%s", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("http request crashed method=%s path=%s", request.method, request.url.path)
        raise
    elapsed_ms = round((time.monotonic() - started_at) * 1000)
    logger.info(
        "http request done method=%s path=%s status=%s elapsed_ms=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    log_method = logger.error if exc.status_code >= 500 else logger.warning
    log_method(
        "http exception method=%s path=%s status=%s detail=%s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


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
        devices = [DeviceDto(serial=d.serial, state=d.state, description=d.description) for d in AdbClient().devices()]
        logger.info("api devices returned count=%s", len(devices))
        return devices
    except AdbError as exc:
        logger.exception("api devices failed")
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
            except WebSocketDisconnect:
                raise
            except Exception as exc:
                logger.exception("device websocket poll failed")
                try:
                    await websocket.send_json({"type": "devices", "devices": [], "error": _error_detail(exc)})
                except WebSocketDisconnect:
                    raise
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
        logger.exception("api screen failed device=%s", device_id)
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
        result = setup_adb_keyboard(device_id)
        logger.info("api adb keyboard setup device=%s ok=%s", device_id, result.get("ok"))
        return result
    except AdbError as exc:
        logger.exception("api adb keyboard setup failed device=%s", device_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/sessions")
def create_session(request: StartSessionRequest):
    try:
        logger.info("api create session device=%s max_steps=%s task=%s", request.device_id, request.max_steps, request.task)
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
        logger.info("api run step session=%s hint=%s", session_id, request.hint)
        return store.step(session_id, request.hint)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    except Exception as exc:
        _raise_logged_500("run session step", exc)


@app.post("/api/sessions/{session_id}/run")
def run_session(session_id: str, request: RunRequest):
    try:
        logger.info("api run session session=%s hint=%s", session_id, request.hint)
        return store.run(session_id, request.hint)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    except Exception as exc:
        _raise_logged_500("run session", exc)


@app.post("/api/sessions/{session_id}/finish")
def finish_session(session_id: str):
    try:
        logger.info("api finish session=%s", session_id)
        return store.finish(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc


@app.post("/api/sessions/{session_id}/replay", response_model=ReplayResponse)
def replay(session_id: str, request: ReplayRequest) -> ReplayResponse:
    logger.info(
        "api replay session=%s targets=%s max_steps=%s gap=%s",
        session_id,
        request.target_device_ids,
        request.max_steps,
        request.device_gap_seconds,
    )
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
