"""F23: the few SmartThings REST calls we need: list devices, read status, send a command, subscribe to events."""

import re
from typing import Any

import httpx

API = "https://api.smartthings.com/v1"
_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def _checked(identifier: str) -> str:
    if not _ID.fullmatch(identifier):
        raise ValueError(f"not a SmartThings id: {identifier!r}")  # ids go into URLs; never trust them blindly
    return identifier


class SmartThingsClient:
    def __init__(self, access_token: str, http: httpx.AsyncClient) -> None:
        self._http = http
        self._headers = {"Authorization": f"Bearer {access_token}"}

    async def _request(self, method: str, path: str, json: Any = None) -> dict[str, Any]:
        response = await self._http.request(method, f"{API}{path}", headers=self._headers, json=json, timeout=10.0)
        response.raise_for_status()
        return response.json() if response.content else {}

    async def devices(self) -> list[dict[str, Any]]:
        return (await self._request("GET", "/devices")).get("items", [])

    async def status(self, device_id: str) -> dict[str, Any]:
        body = await self._request("GET", f"/devices/{_checked(device_id)}/status")
        return body.get("components", {}).get("main", {})

    async def command(self, device_id: str, capability: str, command: str, arguments: list[Any]) -> None:
        body = {
            "commands": [{"component": "main", "capability": capability, "command": command, "arguments": arguments}]
        }
        await self._request("POST", f"/devices/{_checked(device_id)}/commands", json=body)

    async def subscribe(self, installed_app_id: str, device_id: str) -> None:
        body = {
            "sourceType": "DEVICE",
            "device": {"deviceId": _checked(device_id), "componentId": "main", "capability": "*", "attribute": "*",
                       "stateChangeOnly": True, "subscriptionName": f"procasto_{device_id[:8]}"},
        }  # fmt: skip
        await self._request("POST", f"/installedapps/{_checked(installed_app_id)}/subscriptions", json=body)
