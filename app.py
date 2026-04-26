from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from env import Action, EnterpriseEmailTriageEnvironment, available_tasks
from live_email import LiveEmailSession, ProviderType


load_dotenv()


class ResetRequest(BaseModel):
    task_id: Optional[str] = "easy"


class LiveResetRequest(BaseModel):
    provider: ProviderType
    limit: int = 10


app = FastAPI(title="Enterprise Email Triage & Response Environment", version="1.0.0")
environment = EnterpriseEmailTriageEnvironment()
live_session = LiveEmailSession()

GRADIO_MOUNTED = False

# Serve static files (HTML, CSS, JS)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def root():
    """Land judges on the live Gradio UI when available; fall back to the
    static dashboard so the Space still renders if gradio failed to install."""
    if GRADIO_MOUNTED:
        return RedirectResponse(url="/ui/")
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse(
        {
            "message": "OpenEnv Email Triage Environment",
            "health": "/health",
            "docs": "/docs",
            "web": "/web",
            "ui": "/ui",
        }
    )


@app.get("/web")
def web():
    """HF-friendly web entrypoint"""
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/tasks")
def tasks() -> Dict[str, Any]:
    return {"tasks": available_tasks()}


@app.post("/reset")
def reset(payload: Optional[ResetRequest] = None) -> Dict[str, Any]:
    task_id = payload.task_id if payload and payload.task_id else "easy"
    try:
        observation = environment.reset(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"observation": observation.model_dump()}


@app.post("/step")
def step(payload: Action) -> Dict[str, Any]:
    observation, reward, done, info = environment.step(payload)
    return {
        "observation": observation.model_dump(),
        "reward": reward.model_dump(),
        "done": done,
        "info": info,
    }


@app.get("/state")
def state() -> Dict[str, Any]:
    observation = environment.state()
    return {"observation": observation.model_dump()}


@app.get("/dashboard")
def dashboard() -> Dict[str, Any]:
    return {
        "simulation": {
            "available_tasks": available_tasks(),
            "current_state": environment.state().model_dump(),
        },
        "live": live_session.dashboard(),
    }


@app.post("/live/reset")
def live_reset(payload: LiveResetRequest) -> Dict[str, Any]:
    try:
        observation = live_session.reset(payload.provider, payload.limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"observation": observation.model_dump()}


@app.post("/live/step")
def live_step(payload: Action) -> Dict[str, Any]:
    try:
        observation, reward, done, info = live_session.step(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "observation": observation.model_dump(),
        "reward": reward.model_dump(),
        "done": done,
        "info": info,
    }


@app.get("/live/state")
def live_state() -> Dict[str, Any]:
    try:
        observation = live_session.state()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"observation": observation.model_dump()}


@app.get("/live/dashboard")
def live_dashboard() -> Dict[str, Any]:
    try:
        return {"dashboard": live_session.dashboard()}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


try:
    import gradio as gr

    from ui import demo as gradio_demo

    app = gr.mount_gradio_app(app, gradio_demo, path="/ui")
    GRADIO_MOUNTED = True
except Exception as _gradio_exc:
    import logging

    logging.getLogger(__name__).warning(
        "Gradio UI not mounted at /ui (%s: %s). Install `gradio` to enable it.",
        type(_gradio_exc).__name__,
        _gradio_exc,
    )
