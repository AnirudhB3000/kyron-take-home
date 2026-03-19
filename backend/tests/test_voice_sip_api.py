import asyncio
import json
from collections import deque

from fastapi.testclient import TestClient

from app.api.routes import voice as voice_routes
from app.core.dependencies import conversation_service as dependency_conversation_service
from app.core.dependencies import handoff_service as dependency_handoff_service
from app.main import app
from app.schemas.voice import OutboundCallResult


client = TestClient(app)


class StubVoiceAdapter:
    def create_outbound_call(self, handoff_id: str, to_number: str) -> OutboundCallResult:
        return OutboundCallResult(
            call_sid=f"CA{handoff_id[:8]}",
            status="queued",
            to_number=to_number,
            from_number="+18663565614",
        )


class FakeSidebandConnection:
    def __init__(self, queued_events: list[dict] | None = None) -> None:
        self.sent_messages: list[dict] = []
        self.queued_events = deque(json.dumps(event) for event in (queued_events or []))
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent_messages.append(json.loads(message))

    async def recv(self) -> str:
        if self.queued_events:
            return self.queued_events.popleft()
        await asyncio.sleep(3600)
        return ""

    async def close(self) -> None:
        self.closed = True


def test_voice_twiml_returns_sip_dial_when_transport_is_sip(caplog) -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_transport = voice_routes.get_settings().openai_realtime_transport
    original_sip_uri = voice_routes.get_settings().openai_sip_uri
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    try:
        voice_routes.get_settings().openai_realtime_transport = "sip"
        voice_routes.get_settings().openai_sip_uri = "sip:project-123@sip.api.openai.com;transport=tls"
        create_response = client.post("/api/scheduling/conversations")
        conversation_id = create_response.json()["conversation_id"]
        client.patch(
            f"/api/scheduling/conversations/{conversation_id}/intake",
            json={"first_name": "Taylor", "phone_number": "555-123-4567"},
        )
        handoff_response = client.post(f"/api/scheduling/conversations/{conversation_id}/handoff")
        handoff_id = handoff_response.json()["handoff_id"]

        with caplog.at_level("INFO"):
            twiml_response = client.post(f"/api/voice/twiml?handoff_id={handoff_id}")

        assert twiml_response.status_code == 200
        assert '<Dial answerOnBridge="true"><Sip' in twiml_response.text
        assert 'sip:project-123@sip.api.openai.com;transport=tls?x-handoff-id=' in twiml_response.text
        assert f"Voice SIP: returning SIP TwiML for handoff_id={handoff_id}" in caplog.text
        assert f"sip:project-123@sip.api.openai.com;transport=tls?x-handoff-id={handoff_id}" in caplog.text
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.get_settings().openai_realtime_transport = original_transport
        voice_routes.get_settings().openai_sip_uri = original_sip_uri


def test_voice_sip_events_accepts_incoming_call_and_opens_sideband(caplog) -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_connector = voice_routes.openai_realtime_sideband_adapter.connector
    original_accept_call = voice_routes.openai_realtime_sideband_adapter.accept_call
    original_verify_webhook = voice_routes.openai_realtime_sideband_adapter.verify_webhook
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    fake_connection = FakeSidebandConnection()
    accepted_calls: list[tuple[str, dict]] = []

    async def fake_connector(_url, _headers):
        return fake_connection

    async def fake_accept_call(call_id, session):
        accepted_calls.append((call_id, session.model_dump()))
        return {"id": call_id, "status": "in_progress"}

    voice_routes.openai_realtime_sideband_adapter.connector = fake_connector
    voice_routes.openai_realtime_sideband_adapter.accept_call = fake_accept_call
    voice_routes.openai_realtime_sideband_adapter.verify_webhook = lambda body, _headers: json.loads(body)
    try:
        create_response = client.post("/api/scheduling/conversations")
        conversation_id = create_response.json()["conversation_id"]
        client.patch(
            f"/api/scheduling/conversations/{conversation_id}/intake",
            json={"first_name": "Taylor", "phone_number": "555-123-4567"},
        )
        handoff_response = client.post(f"/api/scheduling/conversations/{conversation_id}/handoff")
        handoff_id = handoff_response.json()["handoff_id"]

        with caplog.at_level("INFO"):
            event_response = client.post(
                "/api/voice/sip/events",
                json={
                    "type": "realtime.call.incoming",
                    "data": {
                        "call_id": "call_123",
                        "sip_headers": [
                            {
                                "name": "To",
                                "value": f"sip:project-123@sip.api.openai.com;transport=tls?x-handoff-id={handoff_id}",
                            }
                        ],
                    },
                },
            )

        assert event_response.status_code == 200
        payload = event_response.json()
        assert payload["accepted"] is True
        assert payload["handoff_id"] == handoff_id
        assert payload["openai_session_id"] == "call_123"
        assert accepted_calls[0][0] == "call_123"
        assert accepted_calls[0][1]["instructions"]
        assert fake_connection.sent_messages[0]["type"] == "session.update"

        context_response = client.get(f"/api/scheduling/handoffs/{handoff_id}")
        context = context_response.json()["handoff"]
        assert context["voice_transport"] == "sip"
        assert context["openai_session_id"] == "call_123"
        assert context["sip_call_id"] == "call_123"
        assert "Voice SIP: received webhook request payload_bytes=" in caplog.text
        assert f"Voice SIP: accepting incoming call for handoff_id={handoff_id} openai_session_id=call_123" in caplog.text
        assert f"Voice SIP: sideband listener registered for handoff_id={handoff_id} openai_session_id=call_123" in caplog.text
        assert f"Voice SIP: webhook handled successfully handoff_id={handoff_id} event_type=realtime.call.incoming accepted=True" in caplog.text

        finalize_response = client.post("/api/voice/sip/finalize", json={"handoff_id": handoff_id})
        assert finalize_response.status_code == 200
        assert fake_connection.closed is True
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.openai_realtime_sideband_adapter.connector = original_connector
        voice_routes.openai_realtime_sideband_adapter.accept_call = original_accept_call
        voice_routes.openai_realtime_sideband_adapter.verify_webhook = original_verify_webhook


def test_voice_sip_session_bootstraps_sideband_and_updates_handoff(caplog) -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_connector = voice_routes.openai_realtime_sideband_adapter.connector
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    fake_connection = FakeSidebandConnection()

    async def fake_connector(_url, _headers):
        return fake_connection

    voice_routes.openai_realtime_sideband_adapter.connector = fake_connector
    try:
        create_response = client.post("/api/scheduling/conversations")
        conversation_id = create_response.json()["conversation_id"]
        client.patch(
            f"/api/scheduling/conversations/{conversation_id}/intake",
            json={"first_name": "Taylor", "phone_number": "555-123-4567"},
        )
        handoff_response = client.post(f"/api/scheduling/conversations/{conversation_id}/handoff")
        handoff_id = handoff_response.json()["handoff_id"]
        call_sid = handoff_response.json()["call_sid"]

        with caplog.at_level("INFO"):
            response = client.post(
                "/api/voice/sip/session",
                json={
                    "handoff_id": handoff_id,
                    "openai_session_id": "call_123",
                    "call_sid": call_sid,
                    "sip_call_id": "sip-call-123",
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["voice_transport"] == "sip"
        assert payload["openai_session_id"] == "call_123"

        context_response = client.get(f"/api/scheduling/handoffs/{handoff_id}")
        context = context_response.json()["handoff"]
        assert context["voice_transport"] == "sip"
        assert context["openai_session_id"] == "call_123"
        assert context["sip_call_id"] == "sip-call-123"
        assert fake_connection.sent_messages[0]["type"] == "session.update"
        assert f"Voice SIP: session bootstrap requested handoff_id={handoff_id} openai_session_id=call_123 call_sid={call_sid} sip_call_id=sip-call-123" in caplog.text
        assert f"Voice SIP: session bootstrap completed handoff_id={handoff_id} openai_session_id=call_123 sip_call_id=sip-call-123" in caplog.text

        finalize_response = client.post("/api/voice/sip/finalize", json={"handoff_id": handoff_id})
        assert finalize_response.status_code == 200
        assert fake_connection.closed is True
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.openai_realtime_sideband_adapter.connector = original_connector


def test_voice_sip_events_append_transcript_and_finalize_session() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_connector = voice_routes.openai_realtime_sideband_adapter.connector
    original_verify_webhook = voice_routes.openai_realtime_sideband_adapter.verify_webhook
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    fake_connection = FakeSidebandConnection()

    async def fake_connector(_url, _headers):
        return fake_connection

    voice_routes.openai_realtime_sideband_adapter.connector = fake_connector
    voice_routes.openai_realtime_sideband_adapter.verify_webhook = lambda body, _headers: json.loads(body)
    try:
        create_response = client.post("/api/scheduling/conversations")
        conversation_id = create_response.json()["conversation_id"]
        client.patch(
            f"/api/scheduling/conversations/{conversation_id}/intake",
            json={"first_name": "Taylor", "phone_number": "555-123-4567"},
        )
        handoff_response = client.post(f"/api/scheduling/conversations/{conversation_id}/handoff")
        handoff_id = handoff_response.json()["handoff_id"]

        event_response = client.post(
            "/api/voice/sip/events",
            json={
                "type": "conversation.item.input_audio_transcription.completed",
                "transcript": "I need a Tuesday appointment",
                "headers": {"x-handoff-id": handoff_id},
                "call_id": "call_123",
                "sip_call_id": "sip-call-123",
            },
        )
        assert event_response.status_code == 200

        transcript_response = client.post(
            "/api/voice/sip/transcript",
            json={"handoff_id": handoff_id, "role": "assistant", "content": "I can help with that."},
        )
        assert transcript_response.status_code == 200

        finalize_response = client.post(
            "/api/voice/sip/finalize",
            json={"handoff_id": handoff_id},
        )
        assert finalize_response.status_code == 200

        messages = [message.model_dump() for message in dependency_conversation_service.get_conversation(conversation_id).messages]
        assert messages[-2]["content"] == "I need a Tuesday appointment"
        assert messages[-1]["content"] == "I can help with that."
        context_response = client.get(f"/api/scheduling/handoffs/{handoff_id}")
        assert context_response.json()["handoff"]["realtime_session_status"] == "completed"
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.openai_realtime_sideband_adapter.connector = original_connector
        voice_routes.openai_realtime_sideband_adapter.verify_webhook = original_verify_webhook
