from typing import Any, Literal

from pydantic import BaseModel, Field


AssistantActionName = Literal[
    "respond_to_user",
    "collect_patient_info",
    "match_provider",
    "list_available_slots",
    "filter_available_slots",
    "book_appointment",
    "start_voice_handoff",
]


class AssistantAction(BaseModel):
    action: AssistantActionName
    reply_text: str
    arguments: dict[str, Any] = Field(default_factory=dict)
