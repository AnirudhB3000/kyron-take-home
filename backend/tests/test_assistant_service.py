from app.schemas.assistant_action import AssistantAction
from app.services.assistant_service import AssistantService


class StubOpenAIAdapter:
    def plan_next_action(self, user_message: str, conversation_summary: str, allowed_actions: list[str]) -> AssistantAction:
        return AssistantAction(
            action="collect_patient_info",
            reply_text="I can help with that. First, may I have your first name?",
            arguments={"missing_field": "first_name"},
        )

    def generate_intake_clarification(self, user_message: str, active_field: str, field_prompt: str) -> str:
        return f"I can explain how scheduling works. {field_prompt}"


class FailingClarificationAdapter(StubOpenAIAdapter):
    def generate_intake_clarification(self, user_message: str, active_field: str, field_prompt: str) -> str:
        raise RuntimeError("adapter unavailable")


class BlankClarificationAdapter(StubOpenAIAdapter):
    def generate_intake_clarification(self, user_message: str, active_field: str, field_prompt: str) -> str:
        return "   "


def test_returns_safe_fallback_when_safety_blocks_request() -> None:
    service = AssistantService(openai_adapter=StubOpenAIAdapter())

    result = service.determine_next_action(
        user_message="What medication should I take for this pain?",
        conversation_summary="Patient is asking for next steps.",
    )

    assert result.action == "respond_to_user"
    assert "cannot provide medical advice" in result.reply_text


def test_uses_openai_adapter_for_allowed_request() -> None:
    service = AssistantService(openai_adapter=StubOpenAIAdapter())

    result = service.determine_next_action(
        user_message="I need an appointment for my knee.",
        conversation_summary="New conversation.",
    )

    assert result.action == "collect_patient_info"
    assert result.arguments["missing_field"] == "first_name"


def test_detects_clarification_questions() -> None:
    service = AssistantService(openai_adapter=StubOpenAIAdapter())

    assert service.is_clarification_question("please tell me how this works?") is True
    assert service.is_clarification_question("Taylor") is False


def test_answers_intake_clarification_with_adapter_response() -> None:
    service = AssistantService(openai_adapter=StubOpenAIAdapter())

    reply = service.answer_intake_clarification(
        user_message="what is this?",
        active_field="first_name",
    )

    assert "how scheduling works" in reply
    assert "first name" in reply


def test_falls_back_when_clarification_generation_fails() -> None:
    service = AssistantService(openai_adapter=FailingClarificationAdapter())

    reply = service.answer_intake_clarification(
        user_message="what is this?",
        active_field="first_name",
    )

    assert "virtual scheduling assistant" in reply
    assert "first name" in reply


def test_falls_back_when_clarification_generation_is_blank() -> None:
    service = AssistantService(openai_adapter=BlankClarificationAdapter())

    reply = service.answer_intake_clarification(
        user_message="what is this?",
        active_field="first_name",
    )

    assert "virtual scheduling assistant" in reply
    assert "first name" in reply
