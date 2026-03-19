from types import SimpleNamespace

from app.services.conversation_service import ConversationService
from app.services.handoff_service import HandoffService
from app.services.realtime_voice_service import RealtimeVoiceService
from app.services.scheduling_service import SchedulingService
from app.services.voice_sip_service import VoiceSipService


class StubVoiceAdapter:
    def create_outbound_call(self, handoff_id: str, to_number: str):
        return SimpleNamespace(
            call_sid=f"CA{handoff_id[:8]}",
            status="queued",
            to_number=to_number,
            from_number="+18663565614",
        )


def build_service() -> tuple[ConversationService, HandoffService, VoiceSipService]:
    conversation_service = ConversationService()
    handoff_service = HandoffService(
        conversation_service=conversation_service,
        scheduling_service=SchedulingService(),
        voice_adapter=StubVoiceAdapter(),
    )
    realtime_voice_service = RealtimeVoiceService(
        handoff_service=handoff_service,
        settings=SimpleNamespace(
            openai_realtime_model="gpt-realtime",
            openai_voice_name="alloy",
        ),
    )
    voice_sip_service = VoiceSipService(
        handoff_service=handoff_service,
        realtime_voice_service=realtime_voice_service,
    )
    return conversation_service, handoff_service, voice_sip_service


def test_build_sip_session_marks_transport_and_preserves_context() -> None:
    conversation_service, handoff_service, voice_sip_service = build_service()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(
        conversation.id,
        first_name="Taylor",
        phone_number="555-123-4567",
        appointment_reason="knee pain",
    )

    handoff = handoff_service.create_handoff(conversation.id)
    session = voice_sip_service.build_sip_session(handoff.handoff_id)

    assert session.voice_transport == "sip"
    assert session.openai_session_id is None
    assert "Current workflow step:" in session.instructions
    assert handoff_service.get_handoff_context(handoff.handoff_id).voice_transport == "sip"


def test_attach_openai_session_updates_handoff_context() -> None:
    conversation_service, handoff_service, voice_sip_service = build_service()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(conversation.id, first_name="Taylor", phone_number="555-123-4567")

    handoff = handoff_service.create_handoff(conversation.id)
    voice_sip_service.attach_openai_session(handoff.handoff_id, "sess_123")

    context = handoff_service.get_handoff_context(handoff.handoff_id)
    assert context.openai_session_id == "sess_123"

    updated = conversation_service.get_conversation(conversation.id)
    assert updated.handoff is not None
    assert updated.handoff.openai_session_id == "sess_123"


def test_attach_sip_call_updates_handoff_context() -> None:
    conversation_service, handoff_service, voice_sip_service = build_service()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(conversation.id, first_name="Taylor", phone_number="555-123-4567")

    handoff = handoff_service.create_handoff(conversation.id)
    voice_sip_service.attach_sip_call(handoff.handoff_id, sip_call_id="sip-call-123", call_sid="CAoverride123")

    context = handoff_service.get_handoff_context(handoff.handoff_id)
    assert context.sip_call_id == "sip-call-123"
    assert context.call_sid == "CAoverride123"
    assert context.voice_transport == "sip"


def test_handle_openai_event_appends_transcripts_to_shared_conversation() -> None:
    conversation_service, handoff_service, voice_sip_service = build_service()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(conversation.id, first_name="Taylor", phone_number="555-123-4567")

    handoff = handoff_service.create_handoff(conversation.id)
    voice_sip_service.handle_openai_event(
        handoff.handoff_id,
        {"type": "conversation.item.input_audio_transcription.completed", "transcript": "I need a Tuesday slot"},
    )
    voice_sip_service.handle_openai_event(
        handoff.handoff_id,
        {"type": "response.output_audio_transcript.done", "transcript": "I can help with that."},
    )

    updated = conversation_service.get_conversation(conversation.id)
    assert updated.messages[-2].content == "I need a Tuesday slot"
    assert updated.messages[-2].role == "user"
    assert updated.messages[-1].content == "I can help with that."
    assert updated.messages[-1].role == "assistant"


def test_finalize_session_marks_realtime_completed() -> None:
    conversation_service, handoff_service, voice_sip_service = build_service()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(conversation.id, first_name="Taylor", phone_number="555-123-4567")

    handoff = handoff_service.create_handoff(conversation.id)
    voice_sip_service.finalize_session(handoff.handoff_id)

    assert handoff_service.get_handoff_context(handoff.handoff_id).realtime_session_status == "completed"
