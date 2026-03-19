from datetime import UTC, date, datetime
from uuid import uuid4

from pydantic import BaseModel


class AppointmentSlot(BaseModel):
    slot_id: str
    provider_id: str
    start_at: datetime
    end_at: datetime
    appointment_type: str


class AppointmentBooking(BaseModel):
    conversation_id: str
    slot_id: str
    provider_id: str
    patient_email: str
    patient_phone_number: str
    booked_at: datetime


class AppointmentConfirmation(BaseModel):
    booking: AppointmentBooking
    slot: AppointmentSlot
