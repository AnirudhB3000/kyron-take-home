import asyncio
import logging

from app.core.config import Settings, get_settings
from app.schemas.voice import RealtimeVoiceSession
from app.schemas.voice_sip import SipSessionStartResponse
from app.services.handoff_service import HandoffService
from app.services.realtime_voice_service import RealtimeVoiceService


logger = logging.getLogger(__name__)


class VoiceSipService:
    """Coordinates SIP-oriented OpenAI Realtime session metadata for voice handoffs."""

    def __init__(
        self,
        handoff_service: HandoffService,
        realtime_voice_service: RealtimeVoiceService,
        settings: Settings | None = None,
    ) -> None:
        self.handoff_service = handoff_service
        self.realtime_voice_service = realtime_voice_service
        self.settings = settings or get_settings()
        self.sideband_connections: dict[str, object] = {}
        self.sideband_tasks: dict[str, asyncio.Task] = {}

    def build_sip_uri(self, handoff_id: str) -> str:
        base_uri = self.settings.openai_sip_uri
        if not base_uri and self.settings.openai_project_id:
            base_uri = f"sip:{self.settings.openai_project_id}@sip.api.openai.com;transport=tls"
        if not base_uri:
            raise ValueError("OpenAI SIP is not configured yet. Set OPENAI_PROJECT_ID or OPENAI_SIP_URI.")
        separator = "&" if "?" in base_uri else "?"
        return f"{base_uri}{separator}x-handoff-id={handoff_id}"

    def build_twiml_response(self, handoff_id: str) -> str:
        sip_uri = self.build_sip_uri(handoff_id)
        logger.info(
            "Voice SIP: returning SIP TwiML for handoff_id=%s sip_uri=%s",
            handoff_id,
            sip_uri,
        )
        status_callback = None
        if self.settings.twilio_webhook_base_url:
            status_callback = f'{self.settings.twilio_webhook_base_url.rstrip("/")}/api/voice/status?handoff_id={handoff_id}'
        status_attr = ""
        if status_callback:
            status_attr = (
                f' statusCallback="{status_callback}"'
                ' statusCallbackMethod="POST"'
                ' statusCallbackEvent="initiated ringing answered completed"'
            )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            f'<Dial answerOnBridge="true"><Sip{status_attr}>{sip_uri}</Sip></Dial>'
            '</Response>'
        )

    def build_sip_session(self, handoff_id: str) -> RealtimeVoiceSession:
        self.handoff_service.attach_voice_transport(handoff_id, "sip")
        return self.realtime_voice_service.build_session(handoff_id)

    def build_sip_session_response(self, handoff_id: str) -> SipSessionStartResponse:
        session = self.build_sip_session(handoff_id)
        return SipSessionStartResponse(
            handoff_id=session.handoff_id,
            openai_session_id=session.openai_session_id,
            call_sid=session.call_sid,
            sip_call_id=self.handoff_service.get_handoff_context(handoff_id).sip_call_id,
            voice_transport=session.voice_transport or "sip",
            instructions=session.instructions,
            recent_messages=session.recent_messages,
        )

    def attach_openai_session(self, handoff_id: str, openai_session_id: str) -> None:
        self.handoff_service.attach_openai_session(handoff_id, openai_session_id)

    def attach_sip_call(self, handoff_id: str, sip_call_id: str | None, call_sid: str | None = None) -> None:
        self.handoff_service.attach_sip_call(handoff_id, sip_call_id=sip_call_id, call_sid=call_sid)
        self.handoff_service.attach_voice_transport(handoff_id, "sip")

    def handle_openai_event(self, handoff_id: str, event: dict) -> None:
        event_type = event.get("type")
        if event_type == "response.output_audio_transcript.done":
            self.realtime_voice_service.append_transcript(handoff_id, "assistant", event.get("transcript", ""))
        elif event_type == "response.output_text.done":
            self.realtime_voice_service.append_transcript(handoff_id, "assistant", event.get("text", ""))
        elif event_type == "conversation.item.input_audio_transcription.completed":
            self.realtime_voice_service.append_transcript(handoff_id, "user", event.get("transcript", ""))

    def register_sideband(self, handoff_id: str, connection: object, listener_task: asyncio.Task) -> None:
        self.sideband_connections[handoff_id] = connection
        self.sideband_tasks[handoff_id] = listener_task

    async def close_sideband(self, handoff_id: str, adapter) -> None:
        task = self.sideband_tasks.pop(handoff_id, None)
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        connection = self.sideband_connections.pop(handoff_id, None)
        if connection is not None:
            await adapter.close(connection)

    def finalize_session(self, handoff_id: str) -> None:
        self.handoff_service.mark_realtime_session_completed(handoff_id)
