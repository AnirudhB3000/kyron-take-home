from types import SimpleNamespace

from app.adapters.sms_adapter import SmsAdapter
from app.schemas.notification import SmsConfirmationPayload, SmsOptInPayload


class FakeMessagesClient:
    def __init__(self) -> None:
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(sid="SM1234567890")


class FakeTwilioClient:
    def __init__(self) -> None:
        self.messages = FakeMessagesClient()


def build_settings(**overrides):
    defaults = {
        "twilio_account_sid": "AC123",
        "twilio_auth_token": "secret",
        "twilio_phone_number": "+18663565614",
        "twilio_configured": True,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_send_booking_confirmation_builds_twilio_sms_request() -> None:
    client = FakeTwilioClient()
    adapter = SmsAdapter(client=client, settings=build_settings())

    result = adapter.send_booking_confirmation(
        SmsConfirmationPayload(
            conversation_id="conversation-1",
            recipient_phone_number="+14155550112",
            patient_name="Taylor Morgan",
            provider_name="Dr. Olivia Bennett",
            appointment_start="2026-03-24T09:00:00Z",
        )
    )

    assert result.channel == "sms"
    assert result.message_id == "SM1234567890"
    assert client.messages.kwargs["to"] == "+14155550112"
    assert client.messages.kwargs["from_"] == "+18663565614"
    assert "Dr. Olivia Bennett" in client.messages.kwargs["body"]


def test_send_opt_in_confirmation_builds_twilio_sms_request() -> None:
    client = FakeTwilioClient()
    adapter = SmsAdapter(client=client, settings=build_settings())

    result = adapter.send_opt_in_confirmation(
        SmsOptInPayload(
            conversation_id="conversation-2",
            recipient_phone_number="+14155550112",
            patient_name="Taylor Morgan",
        )
    )

    assert result.channel == "sms"
    assert result.message_id == "SM1234567890"
    assert client.messages.kwargs["to"] == "+14155550112"
    assert client.messages.kwargs["from_"] == "+18663565614"
    assert "signed up for text updates" in client.messages.kwargs["body"]


def test_send_sms_falls_back_to_stub_when_twilio_is_not_configured() -> None:
    adapter = SmsAdapter(settings=build_settings(twilio_configured=False, twilio_phone_number=None))

    result = adapter.send_opt_in_confirmation(
        SmsOptInPayload(
            conversation_id="conversation-3",
            recipient_phone_number="+14155550112",
            patient_name="Taylor Morgan",
        )
    )

    assert result.channel == "sms"
    assert result.delivered is True
    assert "Stub SMS confirmation queued" in result.detail
