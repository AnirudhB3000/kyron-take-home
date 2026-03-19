from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.handoff import VoiceHandoffState


WorkflowStep = Literal[
    "intake",
    "provider_matching",
    "slot_selection",
    "booking_confirmation",
    "completed",
]

MessageRole = Literal["assistant", "user", "system"]


class Message(BaseModel):
    id: str
    role: MessageRole
    content: str
    created_at: datetime


class PatientIntake(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    phone_number: str | None = None
    email: str | None = None
    appointment_reason: str | None = None
    sms_opt_in: bool | None = None


class SchedulingState(BaseModel):
    workflow_step: WorkflowStep = "intake"
    missing_fields: list[str] = Field(default_factory=list)
    matched_provider_id: str | None = None
    selected_slot_id: str | None = None
    active_field: str | None = None


class Conversation(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    intake: PatientIntake = Field(default_factory=PatientIntake)
    scheduling: SchedulingState = Field(default_factory=SchedulingState)
    messages: list[Message] = Field(default_factory=list)
    handoff: VoiceHandoffState | None = None
