from app.schemas.safety import SafetyDecision


class SafetyService:
    """Applies backend safety rules to assistant behavior."""

    UNSAFE_MEDICAL_PATTERNS = [
        "what medication should i take",
        "should i take antibiotics",
        "should i go to the er",
        "am i having a heart attack",
        "diagnose",
        "what treatment should i use",
        "what should i do medically",
        "tell me what medicine",
    ]

    EMERGENCY_PATTERNS = [
        "i died",
        "heart attack",
        "chest pain",
        "can not breathe",
        "can't breathe",
        "trouble breathing",
        "not breathing",
        "stroke",
        "passed out",
        "severe chest pain",
        "suicidal",
        "kill myself",
        "self harm",
        "emergency",
        "help me now",
    ]

    def evaluate(self, user_message: str) -> SafetyDecision:
        normalized_message = user_message.lower()

        if any(pattern in normalized_message for pattern in self.EMERGENCY_PATTERNS):
            return SafetyDecision(
                allowed=False,
                category="emergency",
                reply_text=(
                    "I cannot help with an emergency in chat. If this may be urgent or life-threatening, "
                    "please call emergency services now or contact immediate medical help."
                ),
            )

        if any(pattern in normalized_message for pattern in self.UNSAFE_MEDICAL_PATTERNS):
            return SafetyDecision(
                allowed=False,
                category="medical_advice",
                reply_text=(
                    "I can help with scheduling, office information, and routing your request, "
                    "but I cannot provide medical advice or diagnosis. If this may be urgent or "
                    "an emergency, please contact emergency services or your care team directly."
                ),
            )

        return SafetyDecision(
            allowed=True,
            category="safe",
            reply_text=None,
        )
