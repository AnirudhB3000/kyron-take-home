from datetime import UTC, datetime
from uuid import uuid4

from app.adapters.voice_adapter import VoiceAdapter
from app.schemas.handoff import (
    VoiceHandoffContext,
    VoiceHandoffResponse,
    VoiceHandoffState,
)
from app.services.conversation_service import ConversationService
from app.services.scheduling_service import SchedulingService


class HandoffService:
    """Prepares, validates, and tracks chat-to-voice handoff state."""

    def __init__(
        self,
        conversation_service: ConversationService,
        scheduling_service: SchedulingService,
        voice_adapter: VoiceAdapter | None = None,
    ) -> None:
        self.conversation_service = conversation_service
        self.scheduling_service = scheduling_service
        self.voice_adapter = voice_adapter or VoiceAdapter()
        self.handoffs: dict[str, VoiceHandoffContext] = {}
        self.call_sid_index: dict[str, str] = {}

    def create_handoff(self, conversation_id: str) -> VoiceHandoffResponse:
        conversation = self.conversation_service.get_conversation(conversation_id)
        phone_number = conversation.intake.phone_number
        if not phone_number:
            raise ValueError("A patient phone number is required before continuing by phone.")

        handoff_id = str(uuid4())
        created_at = datetime.now(UTC)

        provider_name = None
        specialty = None
        matched_provider_id = conversation.scheduling.matched_provider_id
        if matched_provider_id:
            provider = self.scheduling_service.get_provider(matched_provider_id)
            provider_name = provider.name
            specialty = provider.specialty

        patient_name = " ".join(
            part for part in [conversation.intake.first_name, conversation.intake.last_name] if part
        )
        patient_summary_parts = []
        if patient_name:
            patient_summary_parts.append(patient_name)
        if conversation.intake.date_of_birth:
            patient_summary_parts.append(f"DOB {conversation.intake.date_of_birth.isoformat()}")
        if conversation.intake.appointment_reason:
            patient_summary_parts.append(f"reason: {conversation.intake.appointment_reason}")
        patient_summary = ", ".join(patient_summary_parts) or "Patient identity is still being collected."

        call_result = self.voice_adapter.create_outbound_call(handoff_id=handoff_id, to_number=phone_number)

        handoff_state = VoiceHandoffState(
            handoff_id=handoff_id,
            destination_phone_number=phone_number,
            status=call_result.status,
            created_at=created_at,
            call_sid=call_result.call_sid,
            call_status=call_result.status,
            stream_sid=None,
            sip_call_id=None,
            voice_transport=None,
            openai_session_id=None,
            realtime_session_status="pending",
        )

        context = VoiceHandoffContext(
            handoff_id=handoff_id,
            conversation_id=conversation.id,
            destination_phone_number=phone_number,
            workflow_step=conversation.scheduling.workflow_step,
            active_field=conversation.scheduling.active_field,
            patient_summary=patient_summary,
            provider_name=provider_name,
            specialty=specialty,
            selected_slot_id=conversation.scheduling.selected_slot_id,
            call_sid=call_result.call_sid,
            call_status=call_result.status,
            stream_sid=None,
            sip_call_id=None,
            voice_transport=None,
            openai_session_id=None,
            realtime_session_status="pending",
            recent_messages=[
                {
                    "role": message.role,
                    "content": message.content,
                    "created_at": message.created_at.isoformat(),
                }
                for message in conversation.messages[-6:]
            ],
        )
        self.handoffs[handoff_id] = context
        self.call_sid_index[call_result.call_sid] = handoff_id

        conversation.handoff = handoff_state
        self.conversation_service.repository.save(conversation)

        return VoiceHandoffResponse(
            handoff_id=handoff_id,
            status=handoff_state.status,
            destination_phone_number=phone_number,
            workflow_step=conversation.scheduling.workflow_step,
            assistant_message=(
                f"I am continuing by phone now. The call to {phone_number} is currently {call_result.status}."
            ),
            call_sid=call_result.call_sid,
            call_status=call_result.status,
            twiml_url=call_result.twiml_url,
            status_callback_url=call_result.status_callback_url,
        )

    def get_handoff_context(self, handoff_id: str) -> VoiceHandoffContext:
        if handoff_id not in self.handoffs:
            raise KeyError(handoff_id)
        return self.handoffs[handoff_id]

    def update_handoff_status(
        self,
        handoff_id: str | None,
        call_sid: str,
        call_status: str,
    ) -> VoiceHandoffContext:
        resolved_handoff_id = handoff_id or self.call_sid_index.get(call_sid)
        if not resolved_handoff_id or resolved_handoff_id not in self.handoffs:
            raise KeyError(handoff_id or call_sid)

        context = self.handoffs[resolved_handoff_id]
        context.call_sid = call_sid
        context.call_status = call_status
        self.handoffs[resolved_handoff_id] = context
        self.call_sid_index[call_sid] = resolved_handoff_id

        conversation = self.conversation_service.get_conversation(context.conversation_id)
        if conversation.handoff is not None:
            conversation.handoff.call_sid = call_sid
            conversation.handoff.call_status = call_status
            conversation.handoff.status = call_status
            self.conversation_service.repository.save(conversation)

        return context

    def attach_stream(
        self,
        handoff_id: str,
        stream_sid: str | None,
        call_sid: str | None,
    ) -> VoiceHandoffContext:
        context = self.get_handoff_context(handoff_id)
        context.stream_sid = stream_sid
        if call_sid:
            context.call_sid = call_sid
            self.call_sid_index[call_sid] = handoff_id
        self.handoffs[handoff_id] = context

        conversation = self.conversation_service.get_conversation(context.conversation_id)
        if conversation.handoff is not None:
            conversation.handoff.stream_sid = stream_sid
            if call_sid:
                conversation.handoff.call_sid = call_sid
            self.conversation_service.repository.save(conversation)
        return context

    def attach_voice_transport(self, handoff_id: str, voice_transport: str) -> VoiceHandoffContext:
        context = self.get_handoff_context(handoff_id)
        context.voice_transport = voice_transport
        self.handoffs[handoff_id] = context

        conversation = self.conversation_service.get_conversation(context.conversation_id)
        if conversation.handoff is not None:
            conversation.handoff.voice_transport = voice_transport
            self.conversation_service.repository.save(conversation)
        return context

    def attach_openai_session(self, handoff_id: str, openai_session_id: str) -> VoiceHandoffContext:
        context = self.get_handoff_context(handoff_id)
        context.openai_session_id = openai_session_id
        self.handoffs[handoff_id] = context

        conversation = self.conversation_service.get_conversation(context.conversation_id)
        if conversation.handoff is not None:
            conversation.handoff.openai_session_id = openai_session_id
            self.conversation_service.repository.save(conversation)
        return context

    def attach_sip_call(
        self,
        handoff_id: str,
        sip_call_id: str | None,
        call_sid: str | None = None,
    ) -> VoiceHandoffContext:
        context = self.get_handoff_context(handoff_id)
        context.sip_call_id = sip_call_id
        if call_sid:
            context.call_sid = call_sid
            self.call_sid_index[call_sid] = handoff_id
        self.handoffs[handoff_id] = context

        conversation = self.conversation_service.get_conversation(context.conversation_id)
        if conversation.handoff is not None:
            conversation.handoff.sip_call_id = sip_call_id
            if call_sid:
                conversation.handoff.call_sid = call_sid
            self.conversation_service.repository.save(conversation)
        return context

    def mark_realtime_session_ready(self, handoff_id: str) -> VoiceHandoffContext:
        return self._set_realtime_status(handoff_id, "connected")

    def mark_realtime_session_completed(self, handoff_id: str) -> VoiceHandoffContext:
        return self._set_realtime_status(handoff_id, "completed")

    def _set_realtime_status(self, handoff_id: str, status: str) -> VoiceHandoffContext:
        context = self.get_handoff_context(handoff_id)
        context.realtime_session_status = status
        self.handoffs[handoff_id] = context

        conversation = self.conversation_service.get_conversation(context.conversation_id)
        if conversation.handoff is not None:
            conversation.handoff.realtime_session_status = status
            self.conversation_service.repository.save(conversation)
        return context

    def build_voice_greeting(self, handoff_id: str) -> str:
        context = self.get_handoff_context(handoff_id)
        parts = [
            "Hello, this is Kyron Medical's scheduling assistant continuing your conversation by phone.",
            f"Your current workflow step is {context.workflow_step.replace('_', ' ')}.",
        ]
        if context.provider_name and context.specialty:
            parts.append(f"You are matched with {context.provider_name} in {context.specialty}.")
        if context.selected_slot_id:
            parts.append(f"Your selected appointment slot is {context.selected_slot_id}.")
        elif context.active_field:
            parts.append(f"The next detail I still need is your {context.active_field.replace('_', ' ')}.")
        parts.append("I have your recent chat context and will continue from there.")
        return " ".join(parts)
