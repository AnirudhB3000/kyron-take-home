from app.adapters.openai_adapter import OpenAIAdapter
from app.schemas.assistant_action import AssistantAction
from app.services.safety_service import SafetyService


DEFAULT_ALLOWED_ACTIONS = [
    "respond_to_user",
    "collect_patient_info",
    "match_provider",
    "list_available_slots",
    "filter_available_slots",
    "book_appointment",
    "start_voice_handoff",
]

FIELD_PROMPTS = {
    "first_name": "To get started, what is your first name?",
    "last_name": "Thanks. What is your last name?",
    "date_of_birth": "What is your date of birth? Please use YYYY-MM-DD.",
    "phone_number": "What is your phone number?",
    "email": "What is your email address?",
    "appointment_reason": "What body part or issue would you like to be seen for?",
}

CLARIFICATION_HINTS = [
    "what is this",
    "what's this",
    "who are you",
    "what are you",
    "wat are you",
    "tell me more",
    "how does this work",
    "how this works",
    "how do you work",
    "i don't understand",
    "i dont understand",
    "help me understand",
    "why do you need",
]


class AssistantService:
    def __init__(
        self,
        openai_adapter: OpenAIAdapter | None = None,
        safety_service: SafetyService | None = None,
    ) -> None:
        self.openai_adapter = openai_adapter or OpenAIAdapter()
        self.safety_service = safety_service or SafetyService()

    def determine_next_action(
        self,
        user_message: str,
        conversation_summary: str,
        allowed_actions: list[str] | None = None,
    ) -> AssistantAction:
        safety_decision = self.safety_service.evaluate(user_message)

        if not safety_decision.allowed:
            return AssistantAction(
                action="respond_to_user",
                reply_text=safety_decision.reply_text,
                arguments={},
            )

        return self.openai_adapter.plan_next_action(
            user_message=user_message,
            conversation_summary=conversation_summary,
            allowed_actions=allowed_actions or DEFAULT_ALLOWED_ACTIONS,
        )

    def is_clarification_question(self, user_message: str) -> bool:
        normalized = user_message.strip().lower()
        return any(hint in normalized for hint in CLARIFICATION_HINTS)

    def answer_intake_clarification(self, user_message: str, active_field: str | None) -> str:
        prompt = FIELD_PROMPTS.get(active_field or "", "Please continue.")
        fallback = (
            "This is Kyron Medical's virtual scheduling assistant. I can help book appointments, "
            "share office information, and continue by phone if needed. I'll keep this simple and "
            f"collect one detail at a time so I can find the right appointment. {prompt}"
        )

        try:
            reply = self.openai_adapter.generate_intake_clarification(
                user_message=user_message,
                active_field=active_field or "unknown",
                field_prompt=prompt,
            )
            if not reply.strip():
                return fallback
            return reply
        except Exception:
            return fallback
