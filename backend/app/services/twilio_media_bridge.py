import json

from app.core.config import Settings, get_settings
from app.services.realtime_voice_service import RealtimeVoiceService


class TwilioMediaBridge:
    """Builds Twilio media-stream contracts for OpenAI Realtime voice continuation."""

    def __init__(
        self,
        realtime_voice_service: RealtimeVoiceService,
        openai_realtime_adapter,
        settings: Settings | None = None,
    ) -> None:
        self.realtime_voice_service = realtime_voice_service
        self.openai_realtime_adapter = openai_realtime_adapter
        self.settings = settings or get_settings()

    def build_stream_url(self) -> str:
        if not self.settings.twilio_webhook_base_url:
            raise ValueError("TWILIO_WEBHOOK_BASE_URL is required for voice media streaming.")
        base_url = self.settings.twilio_webhook_base_url.rstrip("/")
        websocket_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
        return f"{websocket_base}/api/voice/media"

    def build_twiml_response(self, handoff_id: str) -> str:
        stream_url = self.build_stream_url()
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<Response><Connect><Stream url="{stream_url}"><Parameter name="handoff_id" value="{handoff_id}" /></Stream></Connect></Response>'
        )

    def _build_start_openai_events(self, session) -> list[dict]:
        events = [self.openai_realtime_adapter.build_session_update(session)]
        if self.settings.openai_realtime_debug_greeting:
            events.append(
                {
                    "type": "response.create",
                    "response": {
                        "modalities": ["audio", "text"],
                        "instructions": "Say: Hello, this is Kyron Medical calling back to continue our conversation by phone.",
                    },
                }
            )
        return events

    def extract_handoff_id(self, event: dict) -> str | None:
        start = event.get("start", {})
        parameter_groups = [
            start.get("customParameters"),
            start.get("custom_parameters"),
            start.get("parameters"),
        ]

        for parameters in parameter_groups:
            if isinstance(parameters, dict):
                handoff_id = parameters.get("handoff_id") or parameters.get("handoffId")
                if handoff_id:
                    return handoff_id
            elif isinstance(parameters, list):
                for parameter in parameters:
                    if not isinstance(parameter, dict):
                        continue
                    name = parameter.get("name") or parameter.get("Name")
                    value = parameter.get("value") or parameter.get("Value")
                    if name in {"handoff_id", "handoffId"} and value:
                        return value

        return None

    def handle_stream_event(self, handoff_id: str, event: dict) -> dict:
        event_type = event.get("event")
        if event_type == "start":
            stream_sid = event.get("start", {}).get("streamSid")
            call_sid = event.get("start", {}).get("callSid")
            self.realtime_voice_service.handoff_service.attach_stream(
                handoff_id=handoff_id,
                stream_sid=stream_sid,
                call_sid=call_sid,
            )
            session = self.realtime_voice_service.build_session(handoff_id)
            self.realtime_voice_service.handoff_service.mark_realtime_session_ready(handoff_id)
            return {
                "handled": True,
                "event": "start",
                "stream_sid": stream_sid,
                "session": session.model_dump(),
                "openai_events": self._build_start_openai_events(session),
            }
        if event_type == "media":
            payload = event.get("media", {}).get("payload")
            return {
                "handled": True,
                "event": "media",
                "openai_events": [
                    self.openai_realtime_adapter.build_audio_append(payload),
                ],
            }
        if event_type == "mark":
            return {"handled": True, "event": "mark"}
        if event_type == "transcript":
            transcript = event.get("transcript", {})
            role = transcript.get("role", "user")
            content = transcript.get("content", "")
            self.realtime_voice_service.append_transcript(handoff_id, role, content)
            return {"handled": True, "event": "transcript"}
        if event_type == "stop":
            self.realtime_voice_service.handoff_service.mark_realtime_session_completed(handoff_id)
            return {
                "handled": True,
                "event": "stop",
            }
        return {"handled": False, "event": event_type or "unknown"}

    def handle_openai_server_event(self, handoff_id: str, event: dict) -> list[dict]:
        event_type = event.get("type")
        if event_type == "response.output_audio.delta":
            context = self.realtime_voice_service.handoff_service.get_handoff_context(handoff_id)
            if not context.stream_sid:
                return []
            return [
                self.openai_realtime_adapter.build_twilio_media_event(
                    context.stream_sid,
                    event.get("delta", ""),
                )
            ]
        if event_type == "response.output_audio_transcript.done":
            transcript = event.get("transcript", "")
            self.realtime_voice_service.append_transcript(handoff_id, "assistant", transcript)
            return []
        if event_type == "response.output_text.done":
            transcript = event.get("text", "")
            self.realtime_voice_service.append_transcript(handoff_id, "assistant", transcript)
            return []
        if event_type == "conversation.item.input_audio_transcription.completed":
            transcript = event.get("transcript", "")
            self.realtime_voice_service.append_transcript(handoff_id, "user", transcript)
            return []
        return []

    @staticmethod
    def parse_event(raw_text: str) -> dict:
        return json.loads(raw_text)
