from datetime import UTC, datetime

from app.core.data_loader import load_availability, load_providers
from app.schemas.scheduling import AppointmentBooking, AppointmentConfirmation, AppointmentSlot


class SchedulingService:
    """Handles appointment search, filtering, and booking."""

    def __init__(self) -> None:
        self.providers = {provider.id: provider for provider in load_providers()}
        self.slots = {
            slot.slot_id: AppointmentSlot.model_validate(slot.model_dump())
            for slot in load_availability()
        }
        self.bookings: dict[str, AppointmentBooking] = {}

    def list_slots(self, provider_id: str, weekday: str | None = None) -> list[AppointmentSlot]:
        normalized_weekday = weekday.lower() if weekday else None
        available_slots = [
            slot
            for slot in self.slots.values()
            if slot.provider_id == provider_id and slot.slot_id not in self.bookings
        ]

        if normalized_weekday:
            available_slots = [
                slot
                for slot in available_slots
                if slot.start_at.strftime("%A").lower() == normalized_weekday
            ]

        return sorted(available_slots, key=lambda slot: slot.start_at)

    def book_slot(
        self,
        conversation_id: str,
        slot_id: str,
        patient_email: str,
        patient_phone_number: str,
    ) -> AppointmentConfirmation:
        if slot_id in self.bookings:
            raise ValueError("That appointment slot is no longer available.")

        if slot_id not in self.slots:
            raise ValueError("That appointment slot does not exist.")

        slot = self.slots[slot_id]
        booking = AppointmentBooking(
            conversation_id=conversation_id,
            slot_id=slot.slot_id,
            provider_id=slot.provider_id,
            patient_email=patient_email,
            patient_phone_number=patient_phone_number,
            booked_at=datetime.now(UTC),
        )
        self.bookings[slot_id] = booking
        return AppointmentConfirmation(booking=booking, slot=slot)

    def get_provider(self, provider_id: str):
        return self.providers[provider_id]
