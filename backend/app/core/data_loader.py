import json
from pathlib import Path

from app.schemas.availability import AvailabilitySlot
from app.schemas.provider import Provider

ROOT_DIR = Path(__file__).resolve().parents[3]
PROVIDERS_PATH = ROOT_DIR / "shared" / "providers" / "providers.json"
AVAILABILITY_PATH = ROOT_DIR / "shared" / "fixtures" / "availability.json"


def load_providers() -> list[Provider]:
    payload = json.loads(PROVIDERS_PATH.read_text(encoding="utf-8"))
    return [Provider.model_validate(item) for item in payload]


def load_availability() -> list[AvailabilitySlot]:
    payload = json.loads(AVAILABILITY_PATH.read_text(encoding="utf-8"))
    return [AvailabilitySlot.model_validate(item) for item in payload]
