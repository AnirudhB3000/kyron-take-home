from app.services.conversation_service import ConversationService, IntakeValidationError


def test_creates_conversation_with_missing_intake_fields() -> None:
    service = ConversationService()

    conversation = service.create_conversation()

    assert conversation.id
    assert conversation.scheduling.workflow_step == "intake"
    assert conversation.scheduling.active_field == "first_name"
    assert conversation.scheduling.missing_fields == [
        "first_name",
        "last_name",
        "date_of_birth",
        "phone_number",
        "email",
        "appointment_reason",
    ]


def test_updates_intake_and_advances_to_provider_matching() -> None:
    service = ConversationService()
    conversation = service.create_conversation()

    updated = service.update_intake(
        conversation.id,
        first_name="Taylor",
        last_name="Morgan",
        date_of_birth="1990-06-15",
        phone_number="555-123-4567",
        email="taylor@example.com",
        appointment_reason="Knee pain after a run",
        sms_opt_in=True,
    )

    assert updated.intake.first_name == "Taylor"
    assert updated.intake.date_of_birth.isoformat() == "1990-06-15"
    assert updated.intake.sms_opt_in is True
    assert updated.scheduling.missing_fields == []
    assert updated.scheduling.active_field is None
    assert updated.scheduling.workflow_step == "provider_matching"


def test_invalid_first_name_does_not_advance_intake() -> None:
    service = ConversationService()
    conversation = service.create_conversation()

    try:
        service.update_intake(conversation.id, first_name="who")
        assert False, "Expected invalid first name to fail"
    except IntakeValidationError as exc:
        assert exc.field_name == "first_name"

    refreshed = service.get_conversation(conversation.id)
    assert refreshed.intake.first_name is None
    assert refreshed.scheduling.active_field == "first_name"


def test_stores_sms_opt_in_without_affecting_required_fields() -> None:
    service = ConversationService()
    conversation = service.create_conversation()

    updated = service.update_intake(conversation.id, sms_opt_in=False)

    assert updated.intake.sms_opt_in is False
    assert updated.scheduling.active_field == "first_name"
    assert "first_name" in updated.scheduling.missing_fields


def test_future_date_of_birth_is_rejected() -> None:
    service = ConversationService()
    conversation = service.create_conversation()

    try:
        service.update_intake(conversation.id, date_of_birth="2999-01-01")
        assert False, "Expected future DOB to fail"
    except IntakeValidationError as exc:
        assert exc.field_name == "date_of_birth"

    refreshed = service.get_conversation(conversation.id)
    assert refreshed.intake.date_of_birth is None
    assert refreshed.scheduling.active_field == "first_name"


def test_invalid_email_does_not_advance_intake() -> None:
    service = ConversationService()
    conversation = service.create_conversation()

    try:
        service.update_intake(conversation.id, email="bad-email")
        assert False, "Expected invalid email to fail"
    except IntakeValidationError as exc:
        assert exc.field_name == "email"

    refreshed = service.get_conversation(conversation.id)
    assert refreshed.intake.email is None
    assert refreshed.scheduling.active_field == "first_name"


def test_invalid_phone_number_does_not_advance_intake() -> None:
    service = ConversationService()
    conversation = service.create_conversation()

    try:
        service.update_intake(conversation.id, phone_number="12345")
        assert False, "Expected invalid phone number to fail"
    except IntakeValidationError as exc:
        assert exc.field_name == "phone_number"

    refreshed = service.get_conversation(conversation.id)
    assert refreshed.intake.phone_number is None
    assert refreshed.scheduling.active_field == "first_name"


def test_extracts_multiple_intake_fields_from_single_message() -> None:
    service = ConversationService()
    conversation = service.create_conversation()

    updates = service.extract_intake_updates(
        conversation.id,
        "my name jeff marston. my email id is jeff@jeff.com, my phone is 2032020386, my problem is knee pain:",
    )

    assert updates == {
        "email": "jeff@jeff.com",
        "phone_number": "2032020386",
        "first_name": "Jeff",
        "last_name": "Marston",
        "appointment_reason": "knee pain",
    }
