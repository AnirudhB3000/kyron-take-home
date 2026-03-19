from openai import OpenAI

from app.core.config import get_settings
from app.schemas.assistant_action import AssistantAction


class OpenAIAdapter:
    """Wraps backend calls to the OpenAI API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key, timeout=3.0, max_retries=0)
        self.model = "gpt-4.1-mini"

    def plan_next_action(
        self,
        user_message: str,
        conversation_summary: str,
        allowed_actions: list[str],
    ) -> AssistantAction:
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are a medical practice assistant. You must only choose one "
                                "allowed action and provide a safe, non-diagnostic reply."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"Conversation summary: {conversation_summary}\n"
                                f"Allowed actions: {', '.join(allowed_actions)}\n"
                                f"Latest user message: {user_message}"
                            ),
                        }
                    ],
                },
            ],
            text_format=AssistantAction,
        )
        return response.output_parsed

    def generate_intake_clarification(
        self,
        user_message: str,
        active_field: str,
        field_prompt: str,
    ) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are Kyron Medical's scheduling assistant. Answer short patient clarification "
                                "questions about what this assistant is, how scheduling works, or why a detail is needed. "
                                "Do not provide medical advice or invent features. Keep the answer under 60 words and end "
                                "by asking the current intake question again exactly as provided."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"Current intake field: {active_field}\n"
                                f"Current intake prompt: {field_prompt}\n"
                                f"Patient message: {user_message}"
                            ),
                        }
                    ],
                },
            ],
        )
        return response.output_text
