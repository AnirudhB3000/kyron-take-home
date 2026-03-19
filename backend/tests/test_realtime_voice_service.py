from types import SimpleNamespace

from app.services.conversation_service import ConversationService
from app.services.handoff_service import HandoffService
from app.services.realtime_voice_service import RealtimeVoiceService
from app.services.scheduling_service import SchedulingService


class StubVoiceAdapter:
    def create_outbound_call(self, handoff_id: str, to_number: str):
        return SimpleNamespace(
            call_sid=f"CA{handoff_id[:8]}",
            status="queued",
            to_number=to_number,
            from_number="+18663565614",
        )


def build_service() -> tuple[ConversationService, HandoffService, RealtimeVoiceService]:
    conversation_service = ConversationService()
    handoff_service = HandoffService(
        conversation_service=conversation_service,
        scheduling_service=SchedulingService(),
        voice_adapter=StubVoiceAdapter(),
    )
    realtime_voice_service = RealtimeVoiceService(
        handoff_service=handoff_service,
        settings=SimpleNamespace(
            openai_realtime_model="gpt-4o-realtime-preview",
            openai_voice_name="alloy",
        ),
    )
    return conversation_service, handoff_service, realtime_voice_service


def test_build_session_includes_shared_conversation_context() -> None:
    conversation_service, handoff_service, realtime_voice_service = build_service()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(
        conversation.id,
        first_name="Taylor",
        last_name="Morgan",
        phone_number="555-123-4567",
        appointment_reason="knee pain",
    )
    conversation_service.add_message(conversation.id, "assistant", "What is your email address?")
    conversation_service.add_message(conversation.id, "user", "taylor@example.com")

    handoff = handoff_service.create_handoff(conversation.id)
    session = realtime_voice_service.build_session(handoff.handoff_id)

    assert session.model == "gpt-4o-realtime-preview"
    assert session.voice == "alloy"
    assert session.conversation_id == conversation.id
    assert "Current workflow step: intake" in session.instructions
    assert "Patient summary:" in session.instructions
    assert session.recent_messages[-1]["content"] == "taylor@example.com"


def test_append_transcript_writes_back_to_shared_conversation() -> None:
    conversation_service, handoff_service, realtime_voice_service = build_service()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(
        conversation.id,
        first_name="Taylor",
        phone_number="555-123-4567",
    )

    handoff = handoff_service.create_handoff(conversation.id)
    realtime_voice_service.append_transcript(handoff.handoff_id, "user", "I need a Tuesday appointment")

    updated = conversation_service.get_conversation(conversation.id)
    assert updated.messages[-1].content == "I need a Tuesday appointment"
    assert updated.messages[-1].role == "user"


def test_build_session_includes_transport_and_openai_session_metadata() -> None:
    conversation_service, handoff_service, realtime_voice_service = build_service()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(
        conversation.id,
        first_name="Taylor",
        phone_number="555-123-4567",
    )

    handoff = handoff_service.create_handoff(conversation.id)
    handoff_service.attach_voice_transport(handoff.handoff_id, "sip")
    handoff_service.attach_openai_session(handoff.handoff_id, "sess_123")

    session = realtime_voice_service.build_session(handoff.handoff_id)

    assert session.voice_transport == "sip"
    assert session.openai_session_id == "sess_123"
