from app.services.scheduling_service import SchedulingService


service = SchedulingService()


def test_lists_provider_slots_in_time_order() -> None:
    slots = service.list_slots("dr-olivia-bennett")

    assert slots
    assert slots == sorted(slots, key=lambda slot: slot.start_at)


def test_filters_slots_by_weekday() -> None:
    slots = service.list_slots("dr-olivia-bennett", weekday="tuesday")

    assert slots
    assert all(slot.start_at.strftime("%A") == "Tuesday" for slot in slots)


def test_books_slot_once_and_blocks_duplicates() -> None:
    confirmation = service.book_slot(
        conversation_id="conversation-1",
        slot_id="slot-ortho-2026-03-24-0900",
        patient_email="taylor@example.com",
        patient_phone_number="555-123-4567",
    )

    assert confirmation.booking.slot_id == "slot-ortho-2026-03-24-0900"
    assert confirmation.slot.slot_id == "slot-ortho-2026-03-24-0900"

    try:
        service.book_slot(
            conversation_id="conversation-2",
            slot_id="slot-ortho-2026-03-24-0900",
            patient_email="another@example.com",
            patient_phone_number="555-987-6543",
        )
        assert False, "Expected duplicate booking to fail"
    except ValueError as exc:
        assert str(exc) == "That appointment slot is no longer available."


def test_rejects_unknown_slot_ids() -> None:
    try:
        service.book_slot(
            conversation_id="conversation-1",
            slot_id="missing-slot",
            patient_email="taylor@example.com",
            patient_phone_number="555-123-4567",
        )
        assert False, "Expected missing slot to fail"
    except ValueError as exc:
        assert str(exc) == "That appointment slot does not exist."
