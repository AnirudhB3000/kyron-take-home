from fastapi import APIRouter, HTTPException, Query

from app.core.dependencies import (
    assistant_service,
    conversation_service,
    handoff_service,
    notification_service,
    provider_matching_service,
    safety_service,
    scheduling_service,
)
from app.schemas.scheduling_api import (
    BookAppointmentRequest,
    BookAppointmentResponse,
    CreateConversationResponse,
    CreateVoiceHandoffResponse,
    GetVoiceHandoffContextResponse,
    ListSlotsResponse,
    ProcessTurnRequest,
    ProcessTurnResponse,
    ProviderMatchResponse,
    UpdateIntakeRequest,
    UpdateIntakeResponse,
)
from app.services.conversation_service import IntakeValidationError

router = APIRouter()


@router.post("/conversations", response_model=CreateConversationResponse)
def create_conversation() -> CreateConversationResponse:
    conversation = conversation_service.create_conversation()
    return CreateConversationResponse(
        conversation_id=conversation.id,
        workflow_step=conversation.scheduling.workflow_step,
        missing_fields=conversation.scheduling.missing_fields,
        active_field=conversation.scheduling.active_field,
    )


@router.post("/conversations/{conversation_id}/turn", response_model=ProcessTurnResponse)
def process_turn(
    conversation_id: str,
    payload: ProcessTurnRequest,
) -> ProcessTurnResponse:
    try:
        conversation = conversation_service.get_conversation(conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found.") from exc

    message = payload.message.strip()
    safety_decision = safety_service.evaluate(message)
    if not safety_decision.allowed:
        return ProcessTurnResponse(
            handled=True,
            turn_type=safety_decision.category,
            safety_category=safety_decision.category,
            assistant_message=safety_decision.reply_text,
            active_field=conversation.scheduling.active_field,
            workflow_step=conversation.scheduling.workflow_step,
        )

    if assistant_service.is_clarification_question(message):
        return ProcessTurnResponse(
            handled=True,
            turn_type="clarification_question",
            safety_category=None,
            assistant_message=assistant_service.answer_intake_clarification(
                user_message=message,
                active_field=conversation.scheduling.active_field,
            ),
            active_field=conversation.scheduling.active_field,
            workflow_step=conversation.scheduling.workflow_step,
        )

    return ProcessTurnResponse(
        handled=False,
        turn_type="field_answer",
        safety_category=None,
        active_field=conversation.scheduling.active_field,
        workflow_step=conversation.scheduling.workflow_step,
    )


@router.patch("/conversations/{conversation_id}/intake", response_model=UpdateIntakeResponse)
def update_intake(
    conversation_id: str,
    payload: UpdateIntakeRequest,
) -> UpdateIntakeResponse:
    previous_sms_opt_in = None
    try:
        existing_conversation = conversation_service.get_conversation(conversation_id)
        previous_sms_opt_in = existing_conversation.intake.sms_opt_in
        conversation = conversation_service.update_intake(
            conversation_id,
            **payload.model_dump(),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found.") from exc
    except IntakeValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    if payload.sms_opt_in is True and previous_sms_opt_in is not True and conversation.intake.phone_number:
        notification_service.send_sms_opt_in_confirmation(
            conversation_id=conversation.id,
            patient_first_name=conversation.intake.first_name or "",
            patient_last_name=conversation.intake.last_name or "",
            patient_phone_number=conversation.intake.phone_number,
        )

    return UpdateIntakeResponse(
        conversation_id=conversation.id,
        workflow_step=conversation.scheduling.workflow_step,
        missing_fields=conversation.scheduling.missing_fields,
        active_field=conversation.scheduling.active_field,
    )


@router.post("/conversations/{conversation_id}/provider-match", response_model=ProviderMatchResponse)
def match_provider(conversation_id: str) -> ProviderMatchResponse:
    try:
        conversation = conversation_service.get_conversation(conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found.") from exc

    reason = conversation.intake.appointment_reason
    if not reason:
        raise HTTPException(status_code=400, detail="Appointment reason is required.")

    safety_decision = safety_service.evaluate(reason)
    if not safety_decision.allowed:
        conversation_service.reset_appointment_reason(conversation_id)
        return ProviderMatchResponse(
            matched=False,
            reason=safety_decision.reply_text or "This concern cannot be handled in chat.",
            matched_terms=[],
        )

    match_result = provider_matching_service.match_concern(reason)
    if match_result.matched and match_result.provider_id:
        conversation_service.set_matched_provider(conversation_id, match_result.provider_id)
    else:
        conversation_service.reset_appointment_reason(conversation_id)
        match_result.reason = (
            "I could not match that concern to a supported specialty yet. Please describe the body part or issue in different words, such as knee, skin rash, blurry vision, or sinus pain."
        )

    return ProviderMatchResponse(**match_result.model_dump())


@router.get("/conversations/{conversation_id}/slots", response_model=ListSlotsResponse)
def list_slots(
    conversation_id: str,
    weekday: str | None = Query(default=None),
) -> ListSlotsResponse:
    try:
        conversation = conversation_service.get_conversation(conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found.") from exc

    provider_id = conversation.scheduling.matched_provider_id
    if not provider_id:
        raise HTTPException(status_code=400, detail="Provider must be matched first.")

    provider = scheduling_service.get_provider(provider_id)
    slots = scheduling_service.list_slots(provider_id, weekday=weekday)
    serialized_slots = [slot.model_dump(mode="json") for slot in slots]

    return ListSlotsResponse(
        provider_id=provider.id,
        provider_name=provider.name,
        specialty=provider.specialty,
        slots=serialized_slots,
    )


@router.post("/conversations/{conversation_id}/handoff", response_model=CreateVoiceHandoffResponse)
def create_voice_handoff(conversation_id: str) -> CreateVoiceHandoffResponse:
    try:
        handoff = handoff_service.create_handoff(conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CreateVoiceHandoffResponse(**handoff.model_dump())


@router.get("/handoffs/{handoff_id}", response_model=GetVoiceHandoffContextResponse)
def get_voice_handoff_context(handoff_id: str) -> GetVoiceHandoffContextResponse:
    try:
        handoff = handoff_service.get_handoff_context(handoff_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Handoff not found.") from exc

    return GetVoiceHandoffContextResponse(handoff=handoff)


@router.post("/conversations/{conversation_id}/book", response_model=BookAppointmentResponse)
def book_appointment(
    conversation_id: str,
    payload: BookAppointmentRequest,
) -> BookAppointmentResponse:
    try:
        conversation = conversation_service.get_conversation(conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found.") from exc

    if conversation.scheduling.matched_provider_id is None:
        raise HTTPException(status_code=400, detail="Provider must be matched first.")

    if not conversation.intake.email or not conversation.intake.phone_number:
        raise HTTPException(
            status_code=400,
            detail="Patient email and phone number are required before booking.",
        )

    try:
        confirmation = scheduling_service.book_slot(
            conversation_id=conversation_id,
            slot_id=payload.slot_id,
            patient_email=conversation.intake.email,
            patient_phone_number=conversation.intake.phone_number,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    provider = scheduling_service.get_provider(confirmation.booking.provider_id)
    notifications = notification_service.send_booking_confirmations(
        conversation_id=conversation_id,
        patient_first_name=conversation.intake.first_name or "",
        patient_last_name=conversation.intake.last_name or "",
        patient_email=conversation.intake.email,
        patient_phone_number=conversation.intake.phone_number,
        sms_opt_in=bool(conversation.intake.sms_opt_in),
        provider_name=provider.name,
        specialty=provider.specialty,
        slot=confirmation.slot,
    )

    conversation_service.set_selected_slot(conversation_id, payload.slot_id)
    conversation = conversation_service.mark_completed(conversation_id)

    return BookAppointmentResponse(
        conversation_id=confirmation.booking.conversation_id,
        slot_id=confirmation.booking.slot_id,
        provider_id=confirmation.booking.provider_id,
        workflow_step=conversation.scheduling.workflow_step,
        confirmation_message="Your appointment has been booked successfully.",
        notifications=notifications,
    )
