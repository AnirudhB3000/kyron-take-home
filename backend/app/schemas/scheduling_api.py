from pydantic import BaseModel

from app.schemas.handoff import VoiceHandoffContextResponse, VoiceHandoffResponse
from app.schemas.notification import BookingNotifications


class CreateConversationResponse(BaseModel):
    conversation_id: str
    workflow_step: str
    missing_fields: list[str]
    active_field: str | None = None


class UpdateIntakeRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: str | None = None
    phone_number: str | None = None
    email: str | None = None
    appointment_reason: str | None = None
    sms_opt_in: bool | None = None


class ExtractIntakeRequest(BaseModel):
    message: str


class UpdateIntakeResponse(BaseModel):
    conversation_id: str
    workflow_step: str
    missing_fields: list[str]
    active_field: str | None = None
    captured_fields: list[str] = []


class ProcessTurnRequest(BaseModel):
    message: str


class ProcessTurnResponse(BaseModel):
    handled: bool
    turn_type: str
    safety_category: str | None = None
    assistant_message: str | None = None
    active_field: str | None = None
    workflow_step: str


class ProviderMatchResponse(BaseModel):
    matched: bool
    provider_id: str | None = None
    provider_name: str | None = None
    specialty: str | None = None
    matched_terms: list[str]
    reason: str


class ListSlotsResponse(BaseModel):
    provider_id: str
    provider_name: str
    specialty: str
    slots: list[dict]


class BookAppointmentRequest(BaseModel):
    slot_id: str


class BookAppointmentResponse(BaseModel):
    conversation_id: str
    slot_id: str
    provider_id: str
    workflow_step: str
    confirmation_message: str
    notifications: BookingNotifications


class CreateVoiceHandoffResponse(VoiceHandoffResponse):
    pass


class GetVoiceHandoffContextResponse(VoiceHandoffContextResponse):
    pass
