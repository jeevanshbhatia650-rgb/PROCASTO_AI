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

    llm_provider: Literal["fake", "gemini", "tiers"] = "fake"  # anything but "fake" turns on the model tiers
    gemini_api_key: str = ""
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    hf_token: str = ""
    # Tried in order; a tier whose provider has no key is skipped, one that fails rests and the next answers.
    # Gemma 4 is Google's open-weights model on the same free API; each model has its own quota.
    llm_tiers: str = (
        "gemini:gemini-3.1-flash-lite,gemini:gemma-4-26b-a4b-it,gemini:gemini-3.5-flash-lite,"
        "gemini:gemini-flash-lite-latest,gemini:gemma-4-31b-it,groq:llama-3.3-70b-versatile,"
        "openrouter:meta-llama/llama-3.3-70b-instruct:free,hf:openai/gpt-oss-20b"
    )
    llm_tier_timeout_ms: int = 8000  # per model; it rests after this
    llm_hedge_ms: int = 2000  # a model this slow gets the next tier racing alongside it
    smartthings_client_id: str = ""
    smartthings_client_secret: str = ""
    smartthings_redirect_uri: str = "http://localhost:8000/auth/smartthings/callback"
    public_base_url: str = ""
    frontend_url: str = "http://localhost:5180"  # where the SmartThings login returns to
    alexa_skill_id: str = ""  # optional: only answer requests for this skill
    # Accounts. Empty = the site runs as an open demo with no sign-in.
    supabase_url: str = ""
    supabase_publishable_key: str = ""  # public by design; row-level security protects the data
    # Fernet key. SmartThings tokens are encrypted with it before they reach the database.
    token_encryption_key: str = ""
    max_demo_homes: int = 50  # simulated homes for signed-out visitors, one each
    # Behind a reverse proxy you trust (Render, Fly: 1), rate limits key on the address that proxy saw.
    trusted_proxy_hops: int = 0
    # Commands always work on the simulator; real SmartThings devices need this opt-in.
    allow_commands: bool = False
    clause_stability_n: int = 2
    task_timeout_ms: int = 3000
    llm_timeout_ms: int = 1500
    dense_search: bool = True
    embed_threads: int = 0  # 0 = every core; 1 on a small cloud CPU, where extra threads only spin
    sim_seed: int = 7
    cors_origins: list[str] = ["http://localhost:5180", "http://127.0.0.1:5180"]
    cors_origin_regex: str = ""  # e.g. a hosted front end with preview URLs: ^https://procasto[a-z0-9-]*\.vercel\.app$


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
