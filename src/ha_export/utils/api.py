from __future__ import annotations

from typing import Any, Dict, List, Optional
import requests


class HomeAssistantAPI:
    """Thin wrapper around the Home Assistant REST API."""

    def __init__(self, base_url: str, token: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        )
        self._timeout = timeout

    def _request(self, method: str, path: str) -> Any:
        url = f"{self._base_url}{path}"
        response = self._session.request(method, url, timeout=self._timeout)
        response.raise_for_status()
        if not response.content:
            return None
        if "application/json" in response.headers.get("Content-Type", ""):
            return response.json()
        return response.text

    def list_automations(self) -> List[Dict[str, Any]]:
        payload = self._request("GET", "/api/config/automation/config")
        # The API returns {"config": [...]} or a bare list depending on version.
        if isinstance(payload, dict) and "config" in payload:
            return payload.get("config", [])
        if isinstance(payload, list):
            return payload
        return []

    def get_automation(self, automation_id: str) -> Dict[str, Any]:
        payload = self._request("GET", f"/api/config/automation/config/{automation_id}")
        if not isinstance(payload, dict):
            msg = f"Automation {automation_id} response is not a mapping"
            raise ValueError(msg)
        return payload

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "HomeAssistantAPI":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()
