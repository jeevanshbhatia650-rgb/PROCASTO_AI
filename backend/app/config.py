"""Settings from the environment (.env at the repo root)."""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.models import DeviceInfo

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    # Only the repo's own .env. Reading one from the current directory could pick up another project's keys.
    model_config = SettingsConfigDict(env_file=BACKEND_DIR.parent / ".env", extra="ignore")

    device_provider: Literal["sim", "smartthings"] = "sim"
    llm_provider: Literal["fake", "gemini"] = "fake"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    smartthings_client_id: str = ""
    smartthings_client_secret: str = ""
    smartthings_redirect_uri: str = "http://localhost:8000/auth/smartthings/callback"
    public_base_url: str = ""
    frontend_url: str = "http://localhost:5180"  # where the SmartThings login returns to
    # Commands always work on the simulator; real SmartThings devices need this opt-in.
    allow_commands: bool = False
    clause_stability_n: int = 2
    task_timeout_ms: int = 3000
    llm_timeout_ms: int = 1500
    dense_search: bool = True
    sim_seed: int = 7
    cors_origins: list[str] = ["http://localhost:5180", "http://127.0.0.1:5180"]


def load_devices(path: Path = DATA_DIR / "devices.yaml") -> tuple[list[DeviceInfo], dict[str, dict[str, Any]]]:
    """Returns the device list and each device's initial simulated attributes."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    infos: list[DeviceInfo] = []
    initial: dict[str, dict[str, Any]] = {}
    for entry in raw["devices"]:
        attrs = entry.pop("initial", {})
        info = DeviceInfo(**entry)
        infos.append(info)
        initial[info.device_id] = attrs
    return infos, initial
