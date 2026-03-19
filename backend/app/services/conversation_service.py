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
EMAIL_EXTRACTION_PATTERN = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
PHONE_DIGITS_PATTERN = re.compile(r"\d")
PHONE_EXTRACTION_PATTERN = re.compile(
    r"(?<!\d)(?:\+?1[\s\-.()]*)?(?:\(?\d{3}\)?[\s\-.()]*)\d{3}[\s\-.()]?\d{4}(?!\d)"
)
FULL_NAME_PATTERNS = [
    re.compile(r"\bmy name(?:\s+is)?\s+(?P<name>[a-z][a-z\-' ]*[a-z])(?=[,.;:]|$)", re.IGNORECASE),
    re.compile(r"\bi am\s+(?P<name>[a-z][a-z\-' ]*[a-z])(?=[,.;:]|$)", re.IGNORECASE),
    re.compile(r"\bi'm\s+(?P<name>[a-z][a-z\-' ]*[a-z])(?=[,.;:]|$)", re.IGNORECASE),
    re.compile(r"\bthis is\s+(?P<name>[a-z][a-z\-' ]*[a-z])(?=[,.;:]|$)", re.IGNORECASE),
]
EXPLICIT_FIRST_NAME_PATTERN = re.compile(
    r"\bfirst name(?:\s+is)?\s+(?P<name>[a-z][a-z\-']+)", re.IGNORECASE
)
EXPLICIT_LAST_NAME_PATTERN = re.compile(
    r"\blast name(?:\s+is)?\s+(?P<name>[a-z][a-z\-']+)", re.IGNORECASE
)
DOB_PATTERNS = [
    re.compile(r"\b(?P<value>\d{4}-\d{2}-\d{2})\b"),
    re.compile(r"\b(?P<value>\d{1,2}/\d{1,2}/\d{4})\b"),
    re.compile(r"\b(?P<value>\d{1,2}-\d{1,2}-\d{4})\b"),
]
REASON_PATTERNS = [
    re.compile(r"\b(?:my )?problem(?:\s+is|:)\s*(?P<reason>.+)$", re.IGNORECASE),
    re.compile(r"\b(?:my )?issue(?:\s+is|:)\s*(?P<reason>.+)$", re.IGNORECASE),
    re.compile(r"\b(?:appointment )?reason(?:\s+is|:)\s*(?P<reason>.+)$", re.IGNORECASE),
    re.compile(r"\b(?:i need|need help with|need an appointment for)\s+(?P<reason>.+)$", re.IGNORECASE),
    re.compile(r"\b(?:i have|i'm having|im having)\s+(?P<reason>.+)$", re.IGNORECASE),
]
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

    def extract_intake_updates(self, conversation_id: str, message: str) -> dict[str, object]:
        conversation = self.repository.get(conversation_id)
        missing_fields = set(conversation.scheduling.missing_fields)
        extracted: dict[str, object] = {}
        text = message.strip()
        if not text:
            return extracted

        email_match = EMAIL_EXTRACTION_PATTERN.search(text)
        if email_match and "email" in missing_fields:
            extracted["email"] = email_match.group(0)

        phone_match = PHONE_EXTRACTION_PATTERN.search(text)
        if phone_match and "phone_number" in missing_fields:
            extracted["phone_number"] = phone_match.group(0)

        if "date_of_birth" in missing_fields:
            dob = self._extract_date_of_birth(text)
            if dob is not None:
                extracted["date_of_birth"] = dob

        if {"first_name", "last_name"} & missing_fields:
            name_parts = self._extract_full_name(text)
            if name_parts is not None:
                first_name, last_name = name_parts
                if "first_name" in missing_fields:
                    extracted["first_name"] = first_name
                if "last_name" in missing_fields:
                    extracted["last_name"] = last_name
            else:
                explicit_first_name = self._extract_single_name(text, EXPLICIT_FIRST_NAME_PATTERN)
                if explicit_first_name and "first_name" in missing_fields:
                    extracted["first_name"] = explicit_first_name
                explicit_last_name = self._extract_single_name(text, EXPLICIT_LAST_NAME_PATTERN)
                if explicit_last_name and "last_name" in missing_fields:
                    extracted["last_name"] = explicit_last_name

        if "appointment_reason" in missing_fields:
            reason = self._extract_appointment_reason(text)
            if reason:
                extracted["appointment_reason"] = reason

        validated_updates: dict[str, object] = {}
        for field_name, value in extracted.items():
            try:
                normalized_value = self._normalize_value(field_name, value)
                self._validate_field(field_name, normalized_value)
            except IntakeValidationError:
                continue
            validated_updates[field_name] = normalized_value
        return validated_updates

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

    def _extract_full_name(self, text: str) -> tuple[str, str] | None:
        for pattern in FULL_NAME_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            tokens = self._name_tokens(match.group("name"))
            if len(tokens) >= 2:
                return self._normalize_name_token(tokens[0]), " ".join(
                    self._normalize_name_token(token) for token in tokens[1:]
                )
        return None

    def _extract_single_name(self, text: str, pattern: re.Pattern[str]) -> str | None:
        match = pattern.search(text)
        if not match:
            return None
        tokens = self._name_tokens(match.group("name"))
        if len(tokens) != 1:
            return None
        return self._normalize_name_token(tokens[0])

    def _extract_date_of_birth(self, text: str) -> str | None:
        for pattern in DOB_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            raw_value = match.group("value")
            try:
                if "/" in raw_value:
                    month, day_value, year = raw_value.split("/")
                    parsed = date(int(year), int(month), int(day_value))
                elif raw_value.count("-") == 2 and len(raw_value.split("-")[0]) != 4:
                    month, day_value, year = raw_value.split("-")
                    parsed = date(int(year), int(month), int(day_value))
                else:
                    parsed = date.fromisoformat(raw_value)
            except ValueError:
                continue
            return parsed.isoformat()
        return None

    def _extract_appointment_reason(self, text: str) -> str | None:
        for pattern in REASON_PATTERNS:
            match = pattern.search(text)
            if match:
                reason = match.group("reason").strip(" .,:;!?")
                if reason:
                    return reason
        return None

    def _name_tokens(self, value: str) -> list[str]:
        return re.findall(r"[A-Za-z][A-Za-z'-]*", value)

    def _normalize_name_token(self, token: str) -> str:
        return token[:1].upper() + token[1:].lower()
