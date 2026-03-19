from datetime import datetime

from pydantic import BaseModel, Field


class VoiceHandoffState(BaseModel):
    handoff_id: str
    destination_phone_number: str
    status: str
    created_at: datetime
    call_sid: str | None = None
    call_status: str | None = None
    stream_sid: str | None = None
    sip_call_id: str | None = None
    voice_transport: str | None = None
    openai_session_id: str | None = None
    realtime_session_status: str | None = None


class VoiceHandoffContext(BaseModel):
    handoff_id: str
    conversation_id: str
    destination_phone_number: str
    workflow_step: str
    active_field: str | None = None
    patient_summary: str
    provider_name: str | None = None
    specialty: str | None = None
    selected_slot_id: str | None = None
    call_sid: str | None = None
    call_status: str | None = None
    stream_sid: str | None = None
    sip_call_id: str | None = None
    voice_transport: str | None = None
    openai_session_id: str | None = None
    realtime_session_status: str | None = None
    recent_messages: list[dict] = Field(default_factory=list)


class VoiceHandoffResponse(BaseModel):
    handoff_id: str
    status: str
    destination_phone_number: str
    workflow_step: str
    assistant_message: str
    call_sid: str | None = None
    call_status: str | None = None
    twiml_url: str | None = None
    status_callback_url: str | None = None


class VoiceHandoffContextResponse(BaseModel):
    handoff: VoiceHandoffContext
