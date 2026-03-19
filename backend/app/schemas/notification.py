from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class EmailConfirmationPayload(BaseModel):
    conversation_id: str
    recipient_email: str
    patient_name: str
    provider_name: str
    specialty: str
    appointment_start: datetime
    appointment_end: datetime


class SmsConfirmationPayload(BaseModel):
    conversation_id: str
    recipient_phone_number: str
    patient_name: str
    provider_name: str
    appointment_start: datetime


class SmsOptInPayload(BaseModel):
    conversation_id: str
    recipient_phone_number: str
    patient_name: str


class NotificationResult(BaseModel):
    channel: str
    delivered: bool
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    sent_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    detail: str


class BookingNotifications(BaseModel):
    email: NotificationResult
    sms: NotificationResult | None = None
