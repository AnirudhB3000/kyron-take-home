from pydantic import BaseModel


class SafetyDecision(BaseModel):
    allowed: bool
    category: str
    reply_text: str | None = None
