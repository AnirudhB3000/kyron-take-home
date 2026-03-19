from types import SimpleNamespace

from app.adapters.voice_adapter import VoiceAdapter


class FakeCallsClient:
    def __init__(self) -> None:
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(sid="CA1234567890", status="queued")


class FakeTwilioClient:
    def __init__(self) -> None:
        self.calls = FakeCallsClient()


def build_settings(**overrides):
    defaults = {
        "twilio_account_sid": "AC123",
        "twilio_auth_token": "secret",
        "twilio_phone_number": "+18663565614",
        "twilio_webhook_base_url": "https://example.ngrok-free.app",
        "twilio_configured": True,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_create_outbound_call_builds_twilio_request(caplog) -> None:
    client = FakeTwilioClient()
    adapter = VoiceAdapter(client=client, settings=build_settings())

    with caplog.at_level("INFO"):
        result = adapter.create_outbound_call("handoff-123", "+14155550112")

    assert result.call_sid == "CA1234567890"
    assert result.status == "queued"
    assert client.calls.kwargs["to"] == "+14155550112"
    assert client.calls.kwargs["from_"] == "+18663565614"
    assert client.calls.kwargs["url"] == "https://example.ngrok-free.app/api/voice/twiml?handoff_id=handoff-123"
    assert client.calls.kwargs["status_callback"] == "https://example.ngrok-free.app/api/voice/status?handoff_id=handoff-123"
    assert result.twiml_url == "https://example.ngrok-free.app/api/voice/twiml?handoff_id=handoff-123"
    assert result.status_callback_url == "https://example.ngrok-free.app/api/voice/status?handoff_id=handoff-123"
    assert "Voice adapter: creating outbound call handoff_id=handoff-123" in caplog.text
    assert "Voice adapter: outbound call created handoff_id=handoff-123 call_sid=CA1234567890 status=queued" in caplog.text


def test_create_outbound_call_requires_webhook_base_url() -> None:
    adapter = VoiceAdapter(client=FakeTwilioClient(), settings=build_settings(twilio_webhook_base_url=None))

    try:
        adapter.create_outbound_call("handoff-123", "+14155550112")
        assert False, "Expected webhook base URL validation to fail"
    except ValueError as exc:
        assert str(exc) == "TWILIO_WEBHOOK_BASE_URL is required for live outbound calling."
