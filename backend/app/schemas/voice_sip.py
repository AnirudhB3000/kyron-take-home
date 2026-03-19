from pydantic import BaseModel, Field


class SipSessionReference(BaseModel):
    handoff_id: str
    openai_session_id: str | None = None
    call_sid: str | None = None
    sip_call_id: str | None = None
    voice_transport: str = "sip"


class SipSessionStartRequest(BaseModel):
    handoff_id: str
    openai_session_id: str | None = None
    call_sid: str | None = None
    sip_call_id: str | None = None


class SipSessionStartResponse(BaseModel):
    handoff_id: str
    openai_session_id: str | None = None
    call_sid: str | None = None
    sip_call_id: str | None = None
    voice_transport: str = "sip"
    instructions: str
    recent_messages: list[dict] = Field(default_factory=list)


class SipTranscriptEvent(BaseModel):
    handoff_id: str
    role: str
    content: str


class SipFinalizeRequest(BaseModel):
    handoff_id: str
