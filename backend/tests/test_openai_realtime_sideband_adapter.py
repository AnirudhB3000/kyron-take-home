import asyncio
import json

from app.adapters.openai_realtime_sideband_adapter import OpenAIRealtimeSidebandAdapter
from app.schemas.voice import RealtimeVoiceSession


class FakeConnection:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []

    async def send(self, message: str) -> None:
        self.sent_messages.append(json.loads(message))


class FakeWebhookEvent:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def model_dump(self) -> dict:
        return self.payload


class FakeWebhookClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.unwrap_calls: list[tuple[str, dict, str]] = []
        self.webhooks = self

    def unwrap(self, body: str, headers: dict, secret: str):
        self.unwrap_calls.append((body, headers, secret))
        return FakeWebhookEvent(self.payload)


class FakeHttpResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeHttpClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def post(self, url: str, headers: dict, json: dict):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return FakeHttpResponse({"id": "call_123", "status": "in_progress"})


def test_build_connect_url_appends_call_id() -> None:
    adapter = OpenAIRealtimeSidebandAdapter()

    url = adapter.build_connect_url(model="gpt-realtime", call_id="call_123")

    assert url == "wss://api.openai.com/v1/realtime?model=gpt-realtime&call_id=call_123"


def test_send_session_update_uses_realtime_session_payload() -> None:
    adapter = OpenAIRealtimeSidebandAdapter()
    connection = FakeConnection()
    session = RealtimeVoiceSession(
        handoff_id="handoff-123",
        conversation_id="conversation-123",
        model="gpt-realtime",
        voice="alloy",
        instructions="Continue scheduling.",
        recent_messages=[],
    )

    asyncio.run(adapter.send_session_update(connection, session))

    assert connection.sent_messages == [adapter.build_session_update(session)]


def test_verify_webhook_uses_configured_signing_secret(caplog) -> None:
    payload = {"type": "realtime.call.incoming", "data": {"call_id": "call_123"}}
    webhook_client = FakeWebhookClient(payload)
    adapter = OpenAIRealtimeSidebandAdapter(
        settings=type("Settings", (), {"openai_api_key": "sk-test", "openai_webhook_secret": "whsec_test"})(),
        webhook_client=webhook_client,
    )

    with caplog.at_level("INFO"):
        event = adapter.verify_webhook(b'{"type":"ignored"}', {"webhook-id": "wh_123"})

    assert event == payload
    assert "Voice SIP: verifying OpenAI webhook secret_configured=True" in caplog.text
    assert "Voice SIP: webhook signature verified successfully" in caplog.text
    assert webhook_client.unwrap_calls[0][2] == "whsec_test"


def test_accept_call_posts_realtime_session_configuration(caplog) -> None:
    fake_http_client = FakeHttpClient()
    adapter = OpenAIRealtimeSidebandAdapter(
        settings=type("Settings", (), {"openai_api_key": "sk-test", "openai_webhook_secret": None})(),
        http_client_factory=lambda: fake_http_client,
    )
    session = RealtimeVoiceSession(
        handoff_id="handoff-123",
        conversation_id="conversation-123",
        model="gpt-realtime",
        voice="alloy",
        instructions="Continue scheduling.",
        recent_messages=[],
    )

    with caplog.at_level("INFO"):
        response = asyncio.run(adapter.accept_call("call_123", session))

    assert response == {"id": "call_123", "status": "in_progress"}
    assert "Voice SIP: accepting OpenAI call call_id=call_123" in caplog.text
    assert "Voice SIP: accept_call completed via injected client call_id=call_123" in caplog.text
    assert fake_http_client.calls[0]["url"] == "https://api.openai.com/v1/realtime/calls/call_123/accept"
    assert fake_http_client.calls[0]["json"] == {
        "type": "realtime",
        "model": "gpt-realtime",
        "voice": "alloy",
        "instructions": "Continue scheduling.",
    }
