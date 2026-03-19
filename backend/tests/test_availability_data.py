from datetime import datetime

from app.core.data_loader import load_availability, load_providers


MIN_DATE = datetime.fromisoformat("2026-03-17T00:00:00")
MAX_DATE = datetime.fromisoformat("2026-05-16T23:59:59")


def test_availability_fixture_is_valid_for_all_providers() -> None:
    providers = load_providers()
    availability = load_availability()
    provider_ids = {provider.id for provider in providers}
    slot_ids = set()

    assert availability

    seen_provider_ids = set()

    for slot in availability:
        assert slot.slot_id not in slot_ids
        assert slot.provider_id in provider_ids
        assert slot.start_at < slot.end_at
        assert MIN_DATE <= slot.start_at <= MAX_DATE
        assert MIN_DATE <= slot.end_at <= MAX_DATE

        slot_ids.add(slot.slot_id)
        seen_provider_ids.add(slot.provider_id)

    assert seen_provider_ids == provider_ids
