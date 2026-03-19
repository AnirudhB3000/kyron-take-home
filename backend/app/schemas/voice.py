from pydantic import BaseModel, Field


class OutboundCallResult(BaseModel):
    call_sid: str
    status: str
    to_number: str
    from_number: str
    twiml_url: str | None = None
    status_callback_url: str | None = None


class VoiceStatusUpdate(BaseModel):
    handoff_id: str
    call_sid: str
    call_status: str


class RealtimeVoiceSession(BaseModel):
    handoff_id: str
    conversation_id: str
    call_sid: str | None = None
    stream_sid: str | None = None
    voice_transport: str | None = None
    openai_session_id: str | None = None
    model: str
    voice: str
    instructions: str
    recent_messages: list[dict] = Field(default_factory=list)


class VoiceTranscriptEvent(BaseModel):
    handoff_id: str
    role: str
    content: str
