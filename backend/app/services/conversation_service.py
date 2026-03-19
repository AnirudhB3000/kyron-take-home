import re
from datetime import UTC, date, datetime
from uuid import uuid4

from app.schemas.conversation import Conversation, Message, PatientIntake
from app.services.conversation_repository import InMemoryConversationRepository


REQUIRED_INTAKE_FIELDS = [
    "first_name",
    "last_name",
    "date_of_birth",
    "phone_number",
    "email",
    "appointment_reason",
]

NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z\-' ]*$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_DIGITS_PATTERN = re.compile(r"\d")
DISALLOWED_NAME_VALUES = {"who", "what", "why", "huh", "help", "me", "you"}

FIELD_VALIDATION_MESSAGES = {
    "first_name": "Please enter your actual first name using letters.",
    "last_name": "Please enter your actual last name using letters.",
    "date_of_birth": "Please enter a valid date of birth in YYYY-MM-DD format.",
    "phone_number": "Please enter a valid phone number with at least 10 digits.",
    "email": "Please enter a valid email address.",
    "appointment_reason": "Please describe the body part or issue you need help with.",
}


class IntakeValidationError(ValueError):
    def __init__(self, field_name: str, message: str) -> None:
        super().__init__(message)
        self.field_name = field_name
        self.message = message


class ConversationService:
    """Coordinates conversation state and workflow progress."""

    def __init__(self, repository: InMemoryConversationRepository | None = None) -> None:
        self.repository = repository or InMemoryConversationRepository()

    def create_conversation(self) -> Conversation:
        conversation = self.repository.create()
        conversation.scheduling.missing_fields = self._missing_fields(conversation.intake)
        conversation.scheduling.active_field = conversation.scheduling.missing_fields[0]
        return self.repository.save(conversation)

    def add_message(self, conversation_id: str, role: str, content: str) -> Conversation:
        conversation = self.repository.get(conversation_id)
        conversation.messages.append(
            Message(
                id=str(uuid4()),
                role=role,
                content=content,
                created_at=datetime.now(UTC),
            )
        )
        return self.repository.save(conversation)

    def update_intake(self, conversation_id: str, **intake_updates: object) -> Conversation:
        conversation = self.repository.get(conversation_id)
        current_intake = conversation.intake.model_dump()

        for field_name, value in intake_updates.items():
            if value in (None, ""):
                continue
            normalized_value = self._normalize_value(field_name, value)
            self._validate_field(field_name, normalized_value)
            current_intake[field_name] = normalized_value

        conversation.intake = PatientIntake.model_validate(current_intake)
        conversation.scheduling.missing_fields = self._missing_fields(conversation.intake)
        conversation.scheduling.active_field = (
            conversation.scheduling.missing_fields[0]
            if conversation.scheduling.missing_fields
            else None
        )
        conversation.scheduling.workflow_step = self._determine_workflow_step(conversation)
        return self.repository.save(conversation)

    def set_matched_provider(self, conversation_id: str, provider_id: str) -> Conversation:
        conversation = self.repository.get(conversation_id)
        conversation.scheduling.matched_provider_id = provider_id
        conversation.scheduling.active_field = None
        conversation.scheduling.workflow_step = self._determine_workflow_step(conversation)
        return self.repository.save(conversation)

    def reset_appointment_reason(self, conversation_id: str) -> Conversation:
        conversation = self.repository.get(conversation_id)
        conversation.scheduling.active_field = "appointment_reason"
        conversation.scheduling.workflow_step = "provider_matching"
        conversation.scheduling.matched_provider_id = None
        conversation.scheduling.selected_slot_id = None
        return self.repository.save(conversation)

    def set_selected_slot(self, conversation_id: str, slot_id: str) -> Conversation:
        conversation = self.repository.get(conversation_id)
        conversation.scheduling.selected_slot_id = slot_id
        conversation.scheduling.active_field = None
        conversation.scheduling.workflow_step = self._determine_workflow_step(conversation)
        return self.repository.save(conversation)

    def mark_completed(self, conversation_id: str) -> Conversation:
        conversation = self.repository.get(conversation_id)
        conversation.scheduling.workflow_step = "completed"
        conversation.scheduling.active_field = None
        return self.repository.save(conversation)

    def get_conversation(self, conversation_id: str) -> Conversation:
        return self.repository.get(conversation_id)

    def _missing_fields(self, intake: PatientIntake) -> list[str]:
        return [
            field_name
            for field_name in REQUIRED_INTAKE_FIELDS
            if getattr(intake, field_name) in (None, "")
        ]

    def _determine_workflow_step(self, conversation: Conversation) -> str:
        if conversation.scheduling.selected_slot_id:
            return "booking_confirmation"
        if conversation.scheduling.matched_provider_id:
            return "slot_selection"
        if not conversation.scheduling.missing_fields:
            return "provider_matching"
        return "intake"

    def _normalize_value(self, field_name: str, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        if field_name == "date_of_birth" and isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise IntakeValidationError(
                    field_name,
                    FIELD_VALIDATION_MESSAGES[field_name],
                ) from exc
        if field_name == "sms_opt_in":
            if isinstance(value, bool):
                return value
            raise IntakeValidationError(field_name, "Please choose whether you want text updates.")
        return value

    def _validate_field(self, field_name: str, value: object) -> None:
        if field_name in {"first_name", "last_name"}:
            if (
                not isinstance(value, str)
                or not NAME_PATTERN.match(value)
                or value.lower() in DISALLOWED_NAME_VALUES
                or len(value) < 2
            ):
                raise IntakeValidationError(field_name, FIELD_VALIDATION_MESSAGES[field_name])
            return

        if field_name == "date_of_birth":
            if not isinstance(value, date) or value > date.today():
                raise IntakeValidationError(field_name, FIELD_VALIDATION_MESSAGES[field_name])
            return

        if field_name == "phone_number":
            if not isinstance(value, str) or len(PHONE_DIGITS_PATTERN.findall(value)) < 10:
                raise IntakeValidationError(field_name, FIELD_VALIDATION_MESSAGES[field_name])
            return

        if field_name == "email":
            if not isinstance(value, str) or not EMAIL_PATTERN.match(value):
                raise IntakeValidationError(field_name, FIELD_VALIDATION_MESSAGES[field_name])
            return

        if field_name == "appointment_reason":
            if not isinstance(value, str) or len(value) < 3 or not re.search(r"[a-zA-Z]", value):
                raise IntakeValidationError(field_name, FIELD_VALIDATION_MESSAGES[field_name])
