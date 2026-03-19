from app.services.safety_service import SafetyService


service = SafetyService()


def test_blocks_unsafe_medical_advice_requests() -> None:
    decision = service.evaluate("What medication should I take for this pain?")

    assert decision.allowed is False
    assert decision.category == "medical_advice"
    assert "cannot provide medical advice" in decision.reply_text


def test_blocks_emergency_language() -> None:
    decision = service.evaluate("I died 7 minutes ago")

    assert decision.allowed is False
    assert decision.category == "emergency"
    assert "call emergency services" in decision.reply_text


def test_allows_non_medical_scheduling_requests() -> None:
    decision = service.evaluate("I need an appointment for my knee.")

    assert decision.allowed is True
    assert decision.category == "safe"
    assert decision.reply_text is None
