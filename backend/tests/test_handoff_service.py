from app.schemas.voice import OutboundCallResult
from app.services.conversation_service import ConversationService
from app.services.handoff_service import HandoffService
from app.services.scheduling_service import SchedulingService


class StubVoiceAdapter:
    def create_outbound_call(self, handoff_id: str, to_number: str) -> OutboundCallResult:
        return OutboundCallResult(
            call_sid=f"CA{handoff_id[:8]}",
            status="queued",
            to_number=to_number,
            from_number="+18663565614",
        )


def build_services():
    conversation_service = ConversationService()
    scheduling_service = SchedulingService()
    handoff_service = HandoffService(
        conversation_service=conversation_service,
        scheduling_service=scheduling_service,
        voice_adapter=StubVoiceAdapter(),
    )
    return conversation_service, scheduling_service, handoff_service


def test_handoff_requires_phone_number() -> None:
    conversation_service, scheduling_service, handoff_service = build_services()
    conversation = conversation_service.create_conversation()

    try:
        handoff_service.create_handoff(conversation.id)
        assert False, "Expected phone requirement to fail"
    except ValueError as exc:
        assert str(exc) == "A patient phone number is required before continuing by phone."


def test_handoff_context_includes_workflow_and_recent_messages() -> None:
    conversation_service, scheduling_service, handoff_service = build_services()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(
        conversation.id,
        first_name="Taylor",
        last_name="Morgan",
        date_of_birth="1990-06-15",
        phone_number="555-123-4567",
        email="taylor@example.com",
        appointment_reason="knee pain",
    )
    conversation_service.add_message(conversation.id, "assistant", "Hello from chat.")
    conversation_service.add_message(conversation.id, "user", "I want to continue by phone.")
    conversation_service.set_matched_provider(conversation.id, "dr-olivia-bennett")

    response = handoff_service.create_handoff(conversation.id)
    context = handoff_service.get_handoff_context(response.handoff_id)

    assert response.status == "queued"
    assert response.call_sid.startswith("CA")
    assert context.workflow_step == "slot_selection"
    assert context.active_field is None
    assert context.provider_name == "Dr. Olivia Bennett"
    assert context.specialty == "Orthopedics"
    assert len(context.recent_messages) >= 2
    assert "Taylor Morgan" in context.patient_summary
    assert "knee pain" in context.patient_summary
    assert context.voice_transport is None
    assert context.openai_session_id is None
    assert context.sip_call_id is None


def test_handoff_context_preserves_selected_slot_when_present() -> None:
    conversation_service, scheduling_service, handoff_service = build_services()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(
        conversation.id,
        first_name="Jordan",
        last_name="Lee",
        date_of_birth="1992-08-04",
        phone_number="555-321-6543",
        email="jordan@example.com",
        appointment_reason="knee injury",
    )
    conversation_service.set_matched_provider(conversation.id, "dr-olivia-bennett")
    conversation_service.set_selected_slot(conversation.id, "slot-ortho-2026-03-24-0900")

    response = handoff_service.create_handoff(conversation.id)
    context = handoff_service.get_handoff_context(response.handoff_id)

    assert context.selected_slot_id == "slot-ortho-2026-03-24-0900"
    assert context.workflow_step == "booking_confirmation"


def test_handoff_context_preserves_active_field_during_intake() -> None:
    conversation_service, scheduling_service, handoff_service = build_services()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(
        conversation.id,
        first_name="Taylor",
        phone_number="555-123-4567",
    )

    response = handoff_service.create_handoff(conversation.id)
    context = handoff_service.get_handoff_context(response.handoff_id)

    assert context.workflow_step == "intake"
    assert context.active_field == "last_name"


def test_missing_handoff_id_raises_lookup_error() -> None:
    conversation_service, scheduling_service, handoff_service = build_services()

    try:
        handoff_service.get_handoff_context("missing-handoff")
        assert False, "Expected missing handoff lookup to fail"
    except KeyError as exc:
        assert str(exc) == "'missing-handoff'"


def test_handoff_context_truncates_recent_messages_to_last_six() -> None:
    conversation_service, scheduling_service, handoff_service = build_services()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(
        conversation.id,
        first_name="Taylor",
        phone_number="555-123-4567",
    )

    for index in range(8):
        role = "assistant" if index % 2 == 0 else "user"
        conversation_service.add_message(conversation.id, role, f"message-{index}")

    response = handoff_service.create_handoff(conversation.id)
    context = handoff_service.get_handoff_context(response.handoff_id)

    assert len(context.recent_messages) == 6
    assert context.recent_messages[0]["content"] == "message-2"
    assert context.recent_messages[-1]["content"] == "message-7"


def test_handoff_status_updates_by_call_sid() -> None:
    conversation_service, scheduling_service, handoff_service = build_services()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(
        conversation.id,
        first_name="Taylor",
        phone_number="555-123-4567",
    )

    response = handoff_service.create_handoff(conversation.id)
    updated = handoff_service.update_handoff_status(None, response.call_sid, "in-progress")

    assert updated.call_status == "in-progress"
    assert handoff_service.get_handoff_context(response.handoff_id).call_status == "in-progress"


def test_build_voice_greeting_uses_context() -> None:
    conversation_service, scheduling_service, handoff_service = build_services()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(
        conversation.id,
        first_name="Taylor",
        last_name="Morgan",
        date_of_birth="1990-06-15",
        phone_number="555-123-4567",
        email="taylor@example.com",
        appointment_reason="knee pain",
    )
    conversation_service.set_matched_provider(conversation.id, "dr-olivia-bennett")

    response = handoff_service.create_handoff(conversation.id)
    message = handoff_service.build_voice_greeting(response.handoff_id)

    assert "continuing your conversation by phone" in message
    assert "Dr. Olivia Bennett" in message
    assert "slot selection" in message


def test_attach_voice_transport_and_openai_session_update_conversation_handoff() -> None:
    conversation_service, scheduling_service, handoff_service = build_services()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(conversation.id, first_name="Taylor", phone_number="555-123-4567")

    response = handoff_service.create_handoff(conversation.id)
    handoff_service.attach_voice_transport(response.handoff_id, "sip")
    handoff_service.attach_openai_session(response.handoff_id, "sess_123")
    handoff_service.attach_sip_call(response.handoff_id, "sip-call-123", call_sid="CAoverride123")

    context = handoff_service.get_handoff_context(response.handoff_id)
    assert context.voice_transport == "sip"
    assert context.openai_session_id == "sess_123"
    assert context.sip_call_id == "sip-call-123"
    assert context.call_sid == "CAoverride123"

    updated = conversation_service.get_conversation(conversation.id)
    assert updated.handoff is not None
    assert updated.handoff.voice_transport == "sip"
    assert updated.handoff.openai_session_id == "sess_123"
    assert updated.handoff.sip_call_id == "sip-call-123"
