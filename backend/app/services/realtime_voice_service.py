from app.core.config import Settings, get_settings
from app.schemas.voice import RealtimeVoiceSession
from app.services.handoff_service import HandoffService


class RealtimeVoiceService:
    """Builds OpenAI Realtime session context for continued phone conversations."""

    def __init__(
        self,
        handoff_service: HandoffService,
        settings: Settings | None = None,
    ) -> None:
        self.handoff_service = handoff_service
        self.settings = settings or get_settings()

    def build_session(self, handoff_id: str) -> RealtimeVoiceSession:
        context = self.handoff_service.get_handoff_context(handoff_id)
        instructions = self._build_instructions(context)
        return RealtimeVoiceSession(
            handoff_id=context.handoff_id,
            conversation_id=context.conversation_id,
            call_sid=context.call_sid,
            stream_sid=context.stream_sid,
            voice_transport=context.voice_transport,
            openai_session_id=context.openai_session_id,
            model=self.settings.openai_realtime_model,
            voice=self.settings.openai_voice_name,
            instructions=instructions,
            recent_messages=context.recent_messages,
        )

    def append_transcript(self, handoff_id: str, role: str, content: str) -> None:
        context = self.handoff_service.get_handoff_context(handoff_id)
        if not content.strip():
            return
        self.handoff_service.conversation_service.add_message(
            context.conversation_id,
            role,
            content.strip(),
        )

    def _build_instructions(self, context) -> str:
        detail_lines = [
            "You are Kyron Medical's phone assistant continuing an existing web conversation.",
            "You must preserve the same scheduling context, avoid medical advice, and keep the conversation concise and human.",
            f"Conversation ID: {context.conversation_id}",
            f"Current workflow step: {context.workflow_step}",
            f"Active field: {context.active_field or 'none'}",
            f"Patient summary: {context.patient_summary}",
        ]
        if context.provider_name and context.specialty:
            detail_lines.append(
                f"Matched provider: {context.provider_name} ({context.specialty})"
            )
        if context.selected_slot_id:
            detail_lines.append(f"Selected slot: {context.selected_slot_id}")
        if context.recent_messages:
            detail_lines.append("Recent messages:")
            for message in context.recent_messages[-6:]:
                detail_lines.append(f"- {message['role']}: {message['content']}")
        detail_lines.append(
            "If the patient asks for medical advice or presents an emergency, stop normal scheduling and give the same safe fallback used in chat."
        )
        return "\n".join(detail_lines)
