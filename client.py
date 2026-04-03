from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from models import Action


class EmailTriageClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=30.0)

    def close(self) -> None:
        self._client.close()

    def health(self) -> Dict[str, Any]:
        response = self._client.get("/health")
        response.raise_for_status()
        return response.json()

    def reset(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        response = self._client.post("/reset", json={"task_id": task_id})
        response.raise_for_status()
        return response.json()

    def step(self, action: Action | Dict[str, Any]) -> Dict[str, Any]:
        payload = action.model_dump() if isinstance(action, Action) else action
        response = self._client.post("/step", json=payload)
        response.raise_for_status()
        return response.json()

    def state(self) -> Dict[str, Any]:
        response = self._client.get("/state")
        response.raise_for_status()
        return response.json()
