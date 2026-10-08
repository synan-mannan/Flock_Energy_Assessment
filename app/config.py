import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    base_url: str = field(
        default_factory=lambda: os.getenv("URJA_BASE_URL") or "https://urja-ops.flockenergy.tech"
    )
    username: str | None = field(default_factory=lambda: os.getenv("URJA_USERNAME") or None)
    password: str | None = field(default_factory=lambda: os.getenv("URJA_PASSWORD") or None)
    timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("URJA_TIMEOUT_SECONDS") or "10")
    )