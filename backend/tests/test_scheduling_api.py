import asyncio
import json
import logging
from collections import deque

from fastapi.testclient import TestClient

from app.api.routes import scheduling as scheduling_routes
from app.api.routes import voice as voice_routes
from app.core.dependencies import handoff_service as dependency_handoff_service
from app.main import app
from app.schemas.voice import OutboundCallResult


client = TestClient(app)


class StubAssistantService:
    def is_clarification_question(self, user_message: str) -> bool:
        return "what is this" in user_message.lower() or "how this works" in user_message.lower()

    def answer_intake_clarification(self, user_message: str, active_field: str | None) -> str:
        return "This is Kyron Medical's virtual scheduling assistant. To get started, what is your first name?"


class StubVoiceAdapter:
    def create_outbound_call(self, handoff_id: str, to_number: str) -> OutboundCallResult:
        return OutboundCallResult(
            call_sid=f"CA{handoff_id[:8]}",
            status="queued",
            to_number=to_number,
            from_number="+18663565614",
            twiml_url=f"https://example.ngrok-free.app/api/voice/twiml?handoff_id={handoff_id}",
            status_callback_url=f"https://example.ngrok-free.app/api/voice/status?handoff_id={handoff_id}",
        )


class StubNotificationService:
    def __init__(self) -> None:
        self.opt_in_payloads = []
        self.booking_payloads = []

    def send_sms_opt_in_confirmation(self, **kwargs):
        self.opt_in_payloads.append(kwargs)
        return {"channel": "sms", "delivered": True, "detail": "sent"}

    def send_booking_confirmations(self, **kwargs):
        self.booking_payloads.append(kwargs)
        sms_notification = None
        if kwargs.get("sms_opt_in"):
            sms_notification = {
                "channel": "sms",
                "delivered": True,
                "message_id": "sms-1",
                "sent_at": "2026-03-17T12:00:00Z",
                "detail": "sms queued",
            }
        return {
            "email": {
                "channel": "email",
                "delivered": True,
                "message_id": "email-1",
                "sent_at": "2026-03-17T12:00:00Z",
                "detail": "email queued",
            },
            "sms": sms_notification,
        }


class FakeRealtimeConnection:
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


class DelayedRealtimeConnection(FakeRealtimeConnection):
    def __init__(self) -> None:
        super().__init__(queued_events=[{"type": "session.updated"}])
        self.ready = asyncio.Event()

    async def send(self, message: str) -> None:
        await super().send(message)
        payload = json.loads(message)
        if payload.get("type") == "input_audio_buffer.append":
            self.queued_events.append(
                json.dumps({"type": "response.output_audio.delta", "delta": "assistant-audio"})
            )
            self.ready.set()

    async def recv(self) -> str:
        while not self.queued_events:
            await self.ready.wait()
            self.ready.clear()
        return self.queued_events.popleft()


class DelayedAfterManyFramesRealtimeConnection(FakeRealtimeConnection):
    def __init__(self, append_count_before_audio: int) -> None:
        super().__init__(queued_events=[{"type": "session.updated"}])
        self.append_count_before_audio = append_count_before_audio
        self.append_count = 0
        self.ready = asyncio.Event()

    async def send(self, message: str) -> None:
        await super().send(message)
        payload = json.loads(message)
        if payload.get("type") == "input_audio_buffer.append":
            self.append_count += 1
            if self.append_count == self.append_count_before_audio:
                self.queued_events.append(
                    json.dumps({"type": "response.output_audio.delta", "delta": "assistant-audio"})
                )
                self.ready.set()

    async def recv(self) -> str:
        while not self.queued_events:
            await self.ready.wait()
            self.ready.clear()
        return self.queued_events.popleft()


class ServerErrorThenAudioRealtimeConnection(FakeRealtimeConnection):
    def __init__(self) -> None:
        super().__init__(
            queued_events=[
                {"type": "session.created"},
                {"type": "session.updated"},
                {
                    "type": "error",
                    "error": {
                        "type": "server_error",
                        "message": "temporary upstream failure",
                    },
                },
            ]
        )


class SessionUpdatedThenAudioRealtimeConnection(FakeRealtimeConnection):
    def __init__(self) -> None:
        super().__init__(queued_events=[{"type": "session.created"}, {"type": "session.updated"}])
        self.session_updated_delivered = False
        self.append_sent_before_session_updated = False
        self.ready = asyncio.Event()

    async def send(self, message: str) -> None:
        await super().send(message)
        payload = json.loads(message)
        if payload.get("type") == "input_audio_buffer.append":
            if not self.session_updated_delivered:
                self.append_sent_before_session_updated = True
            self.queued_events.append(
                json.dumps({"type": "response.output_audio.delta", "delta": "assistant-audio"})
            )
            self.ready.set()

    async def recv(self) -> str:
        while not self.queued_events:
            await self.ready.wait()
            self.ready.clear()
        message = self.queued_events.popleft()
        if json.loads(message).get("type") == "session.updated":
            self.session_updated_delivered = True
        return message


class BufferedStartupBurstRealtimeConnection(FakeRealtimeConnection):
    def __init__(self) -> None:
        super().__init__(queued_events=[{"type": "session.created"}])
        self.ready = asyncio.Event()
        self.session_updated_released = False
        self.delta_sent = False

    async def send(self, message: str) -> None:
        await super().send(message)
        payload = json.loads(message)
        if payload.get("type") == "input_audio_buffer.append" and not self.delta_sent:
            self.queued_events.append(
                json.dumps({"type": "response.output_audio.delta", "delta": "assistant-audio"})
            )
            self.delta_sent = True
            self.ready.set()

    async def recv(self) -> str:
        if not self.session_updated_released:
            await asyncio.sleep(0.05)
            self.session_updated_released = True
            return json.dumps({"type": "session.updated"})
        while not self.queued_events:
            await self.ready.wait()
            self.ready.clear()
        return self.queued_events.popleft()


class ClosingRealtimeConnection(FakeRealtimeConnection):
    async def recv(self) -> str:
        from websockets.exceptions import ConnectionClosedError

        raise ConnectionClosedError(None, None)


def test_handoff_response_includes_voice_urls() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    try:
        create_response = client.post("/api/scheduling/conversations")
        conversation_id = create_response.json()["conversation_id"]

        intake_response = client.patch(
            f"/api/scheduling/conversations/{conversation_id}/intake",
            json={"first_name": "Taylor", "phone_number": "555-123-4567"},
        )
        assert intake_response.status_code == 200

        handoff_response = client.post(f"/api/scheduling/conversations/{conversation_id}/handoff")

        assert handoff_response.status_code == 200
        payload = handoff_response.json()
        assert payload["twiml_url"].startswith("https://example.ngrok-free.app/api/voice/twiml?handoff_id=")
        assert payload["status_callback_url"].startswith("https://example.ngrok-free.app/api/voice/status?handoff_id=")
    finally:
        dependency_handoff_service.voice_adapter = original_adapter


def test_scheduling_flow_api() -> None:
    create_response = client.post("/api/scheduling/conversations")
    assert create_response.status_code == 200
    conversation_id = create_response.json()["conversation_id"]

    intake_response = client.patch(
        f"/api/scheduling/conversations/{conversation_id}/intake",
        json={
            "first_name": "Taylor",
            "last_name": "Morgan",
            "date_of_birth": "1990-06-15",
            "phone_number": "555-123-4567",
            "email": "taylor@example.com",
            "appointment_reason": "I need an appointment for my knee.",
            "sms_opt_in": True,
        },
    )
    assert intake_response.status_code == 200
    assert intake_response.json()["workflow_step"] == "provider_matching"

    match_response = client.post(
        f"/api/scheduling/conversations/{conversation_id}/provider-match"
    )
    assert match_response.status_code == 200
    assert match_response.json()["provider_id"] == "dr-olivia-bennett"


def test_turn_endpoint_handles_clarification_questions() -> None:
    original_assistant_service = scheduling_routes.assistant_service
    scheduling_routes.assistant_service = StubAssistantService()
    try:
        create_response = client.post("/api/scheduling/conversations")
        conversation_id = create_response.json()["conversation_id"]

        turn_response = client.post(
            f"/api/scheduling/conversations/{conversation_id}/turn",
            json={"message": "what is this site?"},
        )

        assert turn_response.status_code == 200
        payload = turn_response.json()
        assert payload["handled"] is True
        assert payload["turn_type"] == "clarification_question"
        assert payload["safety_category"] is None
        assert "virtual scheduling assistant" in payload["assistant_message"]
        assert payload["active_field"] == "first_name"
    finally:
        scheduling_routes.assistant_service = original_assistant_service


def test_turn_endpoint_handles_emergency_messages() -> None:
    create_response = client.post("/api/scheduling/conversations")
    conversation_id = create_response.json()["conversation_id"]

    turn_response = client.post(
        f"/api/scheduling/conversations/{conversation_id}/turn",
        json={"message": "I died 7 minutes ago"},
    )

    assert turn_response.status_code == 200
    payload = turn_response.json()
    assert payload["handled"] is True
    assert payload["turn_type"] == "emergency"
    assert payload["safety_category"] == "emergency"
    assert "emergency services" in payload["assistant_message"]


def test_turn_endpoint_handles_medical_advice_requests() -> None:
    create_response = client.post("/api/scheduling/conversations")
    conversation_id = create_response.json()["conversation_id"]

    turn_response = client.post(
        f"/api/scheduling/conversations/{conversation_id}/turn",
        json={"message": "What medication should I take for this pain?"},
    )

    assert turn_response.status_code == 200
    payload = turn_response.json()
    assert payload["handled"] is True
    assert payload["turn_type"] == "medical_advice"
    assert payload["safety_category"] == "medical_advice"
    assert payload["active_field"] == "first_name"
    assert payload["workflow_step"] == "intake"
    assert "cannot provide medical advice" in payload["assistant_message"]


def test_unsupported_reason_can_recover_to_successful_slot_listing() -> None:
    create_response = client.post("/api/scheduling/conversations")
    conversation_id = create_response.json()["conversation_id"]

    client.patch(
        f"/api/scheduling/conversations/{conversation_id}/intake",
        json={
            "first_name": "Taylor",
            "last_name": "Morgan",
            "date_of_birth": "1990-06-15",
            "phone_number": "555-123-4567",
            "email": "taylor@example.com",
            "appointment_reason": "stomach pain",
        },
    )

    unsupported_match_response = client.post(
        f"/api/scheduling/conversations/{conversation_id}/provider-match"
    )

    assert unsupported_match_response.status_code == 200
    assert unsupported_match_response.json()["matched"] is False

    retry_intake_response = client.patch(
        f"/api/scheduling/conversations/{conversation_id}/intake",
        json={"appointment_reason": "knee pain"},
    )
    assert retry_intake_response.status_code == 200
    assert retry_intake_response.json()["workflow_step"] == "provider_matching"

    supported_match_response = client.post(
        f"/api/scheduling/conversations/{conversation_id}/provider-match"
    )
    assert supported_match_response.status_code == 200
    assert supported_match_response.json()["matched"] is True
    assert supported_match_response.json()["provider_id"] == "dr-olivia-bennett"

    slot_response = client.get(f"/api/scheduling/conversations/{conversation_id}/slots")
    assert slot_response.status_code == 200
    assert len(slot_response.json()["slots"]) > 0


def test_weekday_filter_returns_only_requested_weekday_slots() -> None:
    create_response = client.post("/api/scheduling/conversations")
    conversation_id = create_response.json()["conversation_id"]

    client.patch(
        f"/api/scheduling/conversations/{conversation_id}/intake",
        json={
            "first_name": "Taylor",
            "last_name": "Morgan",
            "date_of_birth": "1990-06-15",
            "phone_number": "555-123-4567",
            "email": "taylor@example.com",
            "appointment_reason": "knee pain",
        },
    )
    client.post(f"/api/scheduling/conversations/{conversation_id}/provider-match")

    slot_response = client.get(
        f"/api/scheduling/conversations/{conversation_id}/slots?weekday=tuesday"
    )

    assert slot_response.status_code == 200
    payload = slot_response.json()
    assert payload["slots"]
    assert all(slot["start_at"].startswith("2026-03-24") or slot["start_at"].startswith("2026-04-07") or slot["start_at"].startswith("2026-04-28") for slot in payload["slots"])


def test_emergency_reason_returns_safe_fallback() -> None:
    create_response = client.post("/api/scheduling/conversations")
    conversation_id = create_response.json()["conversation_id"]

    client.patch(
        f"/api/scheduling/conversations/{conversation_id}/intake",
        json={
            "first_name": "Taylor",
            "last_name": "Morgan",
            "date_of_birth": "1990-06-15",
            "phone_number": "555-123-4567",
            "email": "taylor@example.com",
            "appointment_reason": "I died 7 minutes ago",
        },
    )

    match_response = client.post(
        f"/api/scheduling/conversations/{conversation_id}/provider-match"
    )

    assert match_response.status_code == 200
    assert match_response.json()["matched"] is False
    assert "call emergency services" in match_response.json()["reason"]


def test_update_intake_sends_opt_in_text_once() -> None:
    original_notification_service = scheduling_routes.notification_service
    scheduling_routes.notification_service = StubNotificationService()
    try:
        create_response = client.post("/api/scheduling/conversations")
        conversation_id = create_response.json()["conversation_id"]

        first_response = client.patch(
            f"/api/scheduling/conversations/{conversation_id}/intake",
            json={
                "first_name": "Taylor",
                "last_name": "Morgan",
                "phone_number": "555-123-4567",
                "sms_opt_in": True,
            },
        )

        assert first_response.status_code == 200
        assert len(scheduling_routes.notification_service.opt_in_payloads) == 1
        assert scheduling_routes.notification_service.opt_in_payloads[0]["patient_phone_number"] == "555-123-4567"

        second_response = client.patch(
            f"/api/scheduling/conversations/{conversation_id}/intake",
            json={"sms_opt_in": True},
        )

        assert second_response.status_code == 200
        assert len(scheduling_routes.notification_service.opt_in_payloads) == 1
    finally:
        scheduling_routes.notification_service = original_notification_service


def test_booking_returns_notification_results() -> None:
    original_notification_service = scheduling_routes.notification_service
    scheduling_routes.notification_service = StubNotificationService()
    try:
        create_response = client.post("/api/scheduling/conversations")
        conversation_id = create_response.json()["conversation_id"]

        client.patch(
            f"/api/scheduling/conversations/{conversation_id}/intake",
            json={
                "first_name": "Taylor",
                "last_name": "Morgan",
                "date_of_birth": "1990-06-15",
                "phone_number": "555-123-4567",
                "email": "taylor@example.com",
                "appointment_reason": "knee pain",
                "sms_opt_in": True,
            },
        )
        client.post(f"/api/scheduling/conversations/{conversation_id}/provider-match")

        booking_response = client.post(
            f"/api/scheduling/conversations/{conversation_id}/book",
            json={"slot_id": "slot-ortho-2026-03-24-0900"},
        )

        assert booking_response.status_code == 200
        payload = booking_response.json()
        assert payload["workflow_step"] == "completed"
        assert payload["notifications"]["email"]["channel"] == "email"
        assert payload["notifications"]["email"]["delivered"] is True
        assert payload["notifications"]["sms"]["channel"] == "sms"
        assert scheduling_routes.notification_service.booking_payloads[0]["sms_opt_in"] is True
    finally:
        scheduling_routes.notification_service = original_notification_service


def test_booking_omits_sms_notification_when_not_opted_in() -> None:
    original_notification_service = scheduling_routes.notification_service
    scheduling_routes.notification_service = StubNotificationService()
    try:
        create_response = client.post("/api/scheduling/conversations")
        conversation_id = create_response.json()["conversation_id"]

        client.patch(
            f"/api/scheduling/conversations/{conversation_id}/intake",
            json={
                "first_name": "Jordan",
                "last_name": "Lee",
                "date_of_birth": "1992-08-04",
                "phone_number": "555-321-6543",
                "email": "jordan@example.com",
                "appointment_reason": "knee injury",
                "sms_opt_in": False,
            },
        )
        client.post(f"/api/scheduling/conversations/{conversation_id}/provider-match")

        booking_response = client.post(
            f"/api/scheduling/conversations/{conversation_id}/book",
            json={"slot_id": "slot-ortho-2026-03-26-1330"},
        )

        assert booking_response.status_code == 200
        payload = booking_response.json()
        assert payload["notifications"]["email"]["channel"] == "email"
        assert payload["notifications"]["sms"] is None
        assert scheduling_routes.notification_service.booking_payloads[0]["sms_opt_in"] is False
    finally:
        scheduling_routes.notification_service = original_notification_service


def test_handoff_endpoint_requires_phone_number() -> None:
    create_response = client.post("/api/scheduling/conversations")
    conversation_id = create_response.json()["conversation_id"]

    handoff_response = client.post(f"/api/scheduling/conversations/{conversation_id}/handoff")

    assert handoff_response.status_code == 400
    assert "phone number" in handoff_response.json()["detail"].lower()


def test_handoff_endpoint_preserves_active_field_during_intake() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    try:
        create_response = client.post("/api/scheduling/conversations")
        conversation_id = create_response.json()["conversation_id"]

        client.patch(
            f"/api/scheduling/conversations/{conversation_id}/intake",
            json={
                "first_name": "Taylor",
                "phone_number": "555-123-4567",
            },
        )

        handoff_response = client.post(f"/api/scheduling/conversations/{conversation_id}/handoff")
        assert handoff_response.status_code == 200

        context_response = client.get(f"/api/scheduling/handoffs/{handoff_response.json()['handoff_id']}")
        assert context_response.status_code == 200
        context_payload = context_response.json()["handoff"]
        assert context_payload["workflow_step"] == "intake"
        assert context_payload["active_field"] == "last_name"
        assert context_payload["call_status"] == "queued"
        assert context_payload["realtime_session_status"] == "pending"
    finally:
        dependency_handoff_service.voice_adapter = original_adapter


def test_handoff_endpoint_returns_live_call_metadata_and_context_lookup() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    try:
        create_response = client.post("/api/scheduling/conversations")
        conversation_id = create_response.json()["conversation_id"]

        client.patch(
            f"/api/scheduling/conversations/{conversation_id}/intake",
            json={
                "first_name": "Taylor",
                "last_name": "Morgan",
                "date_of_birth": "1990-06-15",
                "phone_number": "555-123-4567",
                "email": "taylor@example.com",
                "appointment_reason": "knee pain",
            },
        )
        client.post(f"/api/scheduling/conversations/{conversation_id}/provider-match")

        handoff_response = client.post(f"/api/scheduling/conversations/{conversation_id}/handoff")

        assert handoff_response.status_code == 200
        payload = handoff_response.json()
        assert payload["status"] == "queued"
        assert payload["destination_phone_number"] == "555-123-4567"
        assert payload["call_sid"].startswith("CA")
        assert "continuing by phone" in payload["assistant_message"].lower() or "call to" in payload["assistant_message"].lower()

        context_response = client.get(f"/api/scheduling/handoffs/{payload['handoff_id']}")
        assert context_response.status_code == 200
        context_payload = context_response.json()["handoff"]
        assert context_payload["conversation_id"] == conversation_id
        assert context_payload["destination_phone_number"] == "555-123-4567"
        assert context_payload["provider_name"] == "Dr. Olivia Bennett"
        assert context_payload["workflow_step"] == "slot_selection"
        assert context_payload["call_sid"] == payload["call_sid"]
    finally:
        dependency_handoff_service.voice_adapter = original_adapter


def test_voice_twiml_endpoint_returns_media_stream_xml() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_base_url = voice_routes.twilio_media_bridge.settings.twilio_webhook_base_url
    original_transport = voice_routes.get_settings().openai_realtime_transport
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    voice_routes.twilio_media_bridge.settings.twilio_webhook_base_url = "https://example.ngrok-free.app"
    voice_routes.get_settings().openai_realtime_transport = "media_stream"
    try:
        create_response = client.post("/api/scheduling/conversations")
        conversation_id = create_response.json()["conversation_id"]

        client.patch(
            f"/api/scheduling/conversations/{conversation_id}/intake",
            json={
                "first_name": "Taylor",
                "last_name": "Morgan",
                "date_of_birth": "1990-06-15",
                "phone_number": "555-123-4567",
                "email": "taylor@example.com",
                "appointment_reason": "knee pain",
            },
        )
        client.post(f"/api/scheduling/conversations/{conversation_id}/provider-match")
        handoff_response = client.post(f"/api/scheduling/conversations/{conversation_id}/handoff")

        twiml_response = client.post(f"/api/voice/twiml?handoff_id={handoff_response.json()['handoff_id']}")

        assert twiml_response.status_code == 200
        assert "application/xml" in twiml_response.headers["content-type"]
        assert "<Connect><Stream" in twiml_response.text
        assert '<Parameter name="handoff_id"' in twiml_response.text
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.twilio_media_bridge.settings.twilio_webhook_base_url = original_base_url
        voice_routes.get_settings().openai_realtime_transport = original_transport


def test_voice_status_endpoint_updates_handoff_status() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    try:
        create_response = client.post("/api/scheduling/conversations")
        conversation_id = create_response.json()["conversation_id"]

        client.patch(
            f"/api/scheduling/conversations/{conversation_id}/intake",
            json={
                "first_name": "Taylor",
                "phone_number": "555-123-4567",
            },
        )
        handoff_response = client.post(f"/api/scheduling/conversations/{conversation_id}/handoff")
        handoff_id = handoff_response.json()["handoff_id"]
        call_sid = handoff_response.json()["call_sid"]

        status_response = client.post(
            f"/api/voice/status?handoff_id={handoff_id}",
            content=f"CallSid={call_sid}&CallStatus=in-progress",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

        assert status_response.status_code == 200
        assert status_response.json()["call_status"] == "in-progress"

        context_response = client.get(f"/api/scheduling/handoffs/{handoff_id}")
        assert context_response.json()["handoff"]["call_status"] == "in-progress"
    finally:
        dependency_handoff_service.voice_adapter = original_adapter


def test_voice_media_websocket_logs_disconnect_before_first_frame(caplog) -> None:
    with caplog.at_level(logging.ERROR):
        with client.websocket_connect("/api/voice/media"):
            pass

    assert "Voice media: websocket disconnected before first Twilio stream event" in caplog.text


def test_voice_media_websocket_times_out_before_first_frame(monkeypatch, caplog) -> None:
    async def fake_wait_for(awaitable, timeout):
        awaitable.close()
        raise asyncio.TimeoutError

    monkeypatch.setattr(voice_routes.asyncio, "wait_for", fake_wait_for)

    with caplog.at_level(logging.ERROR):
        with client.websocket_connect("/api/voice/media") as websocket:
            close_message = websocket.receive()

    assert close_message["type"] == "websocket.close"
    assert close_message["code"] == 1008
    assert "Voice media: timed out waiting for first Twilio stream event" in caplog.text


def test_voice_media_websocket_accepts_connected_then_start_sequence() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_connector = voice_routes.twilio_media_bridge.openai_realtime_adapter.connector
    original_debug_greeting = voice_routes.twilio_media_bridge.settings.openai_realtime_debug_greeting
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    fake_connection = FakeRealtimeConnection()

    async def fake_connector(_url, _headers):
        return fake_connection

    voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = fake_connector
    voice_routes.twilio_media_bridge.settings.openai_realtime_debug_greeting = False
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

        with client.websocket_connect("/api/voice/media") as websocket:
            websocket.send_json({"event": "connected", "protocol": "Call", "version": "1.0.0"})
            websocket.send_json(
                {
                    "event": "start",
                    "start": {
                        "streamSid": "MZ789",
                        "callSid": call_sid,
                        "parameters": [
                            {"name": "handoff_id", "value": handoff_id},
                        ],
                    },
                }
            )
            websocket.send_json({"event": "stop"})

        context_response = client.get(f"/api/scheduling/handoffs/{handoff_id}")
        assert context_response.status_code == 200
        assert context_response.json()["handoff"]["stream_sid"] == "MZ789"
        assert fake_connection.closed is True
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = original_connector
        voice_routes.twilio_media_bridge.settings.openai_realtime_debug_greeting = original_debug_greeting
        voice_routes.twilio_media_bridge.settings.openai_realtime_debug_greeting = original_debug_greeting


def test_voice_media_websocket_accepts_parameter_list_start_shape() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_connector = voice_routes.twilio_media_bridge.openai_realtime_adapter.connector
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    fake_connection = FakeRealtimeConnection()

    async def fake_connector(_url, _headers):
        return fake_connection

    voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = fake_connector
    voice_routes.twilio_media_bridge.settings.openai_realtime_debug_greeting = False
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

        with client.websocket_connect("/api/voice/media") as websocket:
            websocket.send_json(
                {
                    "event": "start",
                    "start": {
                        "streamSid": "MZ456",
                        "callSid": call_sid,
                        "parameters": [
                            {"name": "handoff_id", "value": handoff_id},
                        ],
                    },
                }
            )
            websocket.send_json({"event": "stop"})

        context_response = client.get(f"/api/scheduling/handoffs/{handoff_id}")
        assert context_response.status_code == 200
        assert context_response.json()["handoff"]["stream_sid"] == "MZ456"
        assert fake_connection.closed is True
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = original_connector



def test_voice_media_websocket_buffers_startup_audio_until_session_updated() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_connector = voice_routes.twilio_media_bridge.openai_realtime_adapter.connector
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    fake_connection = SessionUpdatedThenAudioRealtimeConnection()

    async def fake_connector(_url, _headers):
        return fake_connection

    voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = fake_connector
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

        with client.websocket_connect("/api/voice/media") as websocket:
            websocket.send_json(
                {
                    "event": "start",
                    "start": {
                        "streamSid": "MZBUFFER",
                        "callSid": call_sid,
                        "customParameters": {"handoff_id": handoff_id},
                    },
                }
            )
            websocket.send_json({"event": "media", "media": {"payload": "caller-audio"}})
            audio_event = websocket.receive_json()
            assert audio_event == {
                "event": "media",
                "streamSid": "MZBUFFER",
                "media": {"payload": "assistant-audio"},
            }
            websocket.send_json({"event": "stop"})

        assert fake_connection.append_sent_before_session_updated is False
        assert fake_connection.sent_messages[0]["type"] == "session.update"
        assert fake_connection.sent_messages[1] == {
            "type": "input_audio_buffer.append",
            "audio": "caller-audio",
        }
        assert fake_connection.closed is True
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = original_connector


def test_voice_media_websocket_caps_startup_audio_buffer_before_session_updated() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_connector = voice_routes.twilio_media_bridge.openai_realtime_adapter.connector
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    fake_connection = BufferedStartupBurstRealtimeConnection()

    async def fake_connector(_url, _headers):
        return fake_connection

    voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = fake_connector
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

        with client.websocket_connect("/api/voice/media") as websocket:
            websocket.send_json(
                {
                    "event": "start",
                    "start": {
                        "streamSid": "MZCAP",
                        "callSid": call_sid,
                        "customParameters": {"handoff_id": handoff_id},
                    },
                }
            )
            for index in range(voice_routes.STARTUP_BUFFER_MAX_EVENTS + 5):
                websocket.send_json(
                    {
                        "event": "media",
                        "media": {"payload": f"caller-audio-{index}"},
                    }
                )
            audio_event = websocket.receive_json()
            assert audio_event == {
                "event": "media",
                "streamSid": "MZCAP",
                "media": {"payload": "assistant-audio"},
            }
            websocket.send_json({"event": "stop"})

        buffered_append_messages = [
            message["audio"]
            for message in fake_connection.sent_messages
            if message.get("type") == "input_audio_buffer.append"
        ]
        expected_payloads = [
            f"caller-audio-{index}"
            for index in range(5, voice_routes.STARTUP_BUFFER_MAX_EVENTS + 5)
        ]
        assert buffered_append_messages == expected_payloads
        assert fake_connection.closed is True
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = original_connector


def test_voice_media_websocket_start_sends_debug_greeting_when_enabled() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_connector = voice_routes.twilio_media_bridge.openai_realtime_adapter.connector
    original_debug_greeting = voice_routes.twilio_media_bridge.settings.openai_realtime_debug_greeting
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    fake_connection = FakeRealtimeConnection()

    async def fake_connector(_url, _headers):
        return fake_connection

    voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = fake_connector
    voice_routes.twilio_media_bridge.settings.openai_realtime_debug_greeting = True
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

        with client.websocket_connect("/api/voice/media") as websocket:
            websocket.send_json(
                {
                    "event": "start",
                    "start": {
                        "streamSid": "MZDBG",
                        "callSid": call_sid,
                        "customParameters": {"handoff_id": handoff_id},
                    },
                }
            )
            websocket.send_json({"event": "stop"})

        assert fake_connection.sent_messages[0]["type"] == "session.update"
        assert fake_connection.sent_messages[1]["type"] == "response.create"
        assert "Kyron Medical calling back" in fake_connection.sent_messages[1]["response"]["instructions"]
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = original_connector
        voice_routes.twilio_media_bridge.settings.openai_realtime_debug_greeting = original_debug_greeting


def test_voice_media_websocket_retries_openai_server_error_once() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_connector = voice_routes.twilio_media_bridge.openai_realtime_adapter.connector
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    first_connection = ServerErrorThenAudioRealtimeConnection()
    second_connection = FakeRealtimeConnection(
        queued_events=[
            {"type": "session.created"},
            {"type": "session.updated"},
            {"type": "response.output_audio.delta", "delta": "assistant-audio"},
        ]
    )
    connections = [first_connection, second_connection]

    async def fake_connector(_url, _headers):
        return connections.pop(0)

    voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = fake_connector
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

        with client.websocket_connect("/api/voice/media") as websocket:
            websocket.send_json(
                {
                    "event": "start",
                    "start": {
                        "streamSid": "MZRETRY",
                        "callSid": call_sid,
                        "customParameters": {"handoff_id": handoff_id},
                    },
                }
            )
            audio_event = websocket.receive_json()
            assert audio_event == {
                "event": "media",
                "streamSid": "MZRETRY",
                "media": {"payload": "assistant-audio"},
            }
            websocket.send_json({"event": "stop"})

        assert first_connection.closed is True
        assert second_connection.closed is True
        assert first_connection.sent_messages[0]["type"] == "session.update"
        assert second_connection.sent_messages[0]["type"] == "session.update"
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = original_connector


def test_voice_media_websocket_handles_openai_connection_closed_error() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_connector = voice_routes.twilio_media_bridge.openai_realtime_adapter.connector
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    fake_connection = ClosingRealtimeConnection()

    async def fake_connector(_url, _headers):
        return fake_connection

    voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = fake_connector
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

        with client.websocket_connect("/api/voice/media") as websocket:
            websocket.send_json(
                {
                    "event": "start",
                    "start": {
                        "streamSid": "MZCLOSE",
                        "callSid": call_sid,
                        "customParameters": {"handoff_id": handoff_id},
                    },
                }
            )
            websocket.send_json({"event": "media", "media": {"payload": "caller-audio"}})
            close_message = websocket.receive()

        assert close_message["type"] == "websocket.close"
        assert close_message["code"] == 1011
        assert fake_connection.closed is True
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = original_connector


def test_voice_media_websocket_returns_exact_twilio_media_payload_for_openai_audio() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_connector = voice_routes.twilio_media_bridge.openai_realtime_adapter.connector
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    fake_connection = FakeRealtimeConnection(
        queued_events=[
            {"type": "session.updated"},
            {"type": "response.output_audio.delta", "delta": "assistant-audio"},
        ]
    )

    async def fake_connector(_url, _headers):
        return fake_connection

    voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = fake_connector
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

        with client.websocket_connect("/api/voice/media") as websocket:
            websocket.send_json(
                {
                    "event": "start",
                    "start": {
                        "streamSid": "MZPAYLOAD",
                        "callSid": call_sid,
                        "customParameters": {"handoff_id": handoff_id},
                    },
                }
            )
            audio_event = websocket.receive_json()
            assert audio_event == {
                "event": "media",
                "streamSid": "MZPAYLOAD",
                "media": {"payload": "assistant-audio"},
            }
            websocket.send_json({"event": "stop"})
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = original_connector


def test_voice_media_websocket_relays_delayed_audio_without_extra_caller_frame() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_connector = voice_routes.twilio_media_bridge.openai_realtime_adapter.connector
    original_debug_greeting = voice_routes.twilio_media_bridge.settings.openai_realtime_debug_greeting
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    fake_connection = DelayedRealtimeConnection()

    async def fake_connector(_url, _headers):
        return fake_connection

    voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = fake_connector
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

        with client.websocket_connect("/api/voice/media") as websocket:
            websocket.send_json(
                {
                    "event": "start",
                    "start": {
                        "streamSid": "MZ124",
                        "callSid": call_sid,
                        "customParameters": {"handoff_id": handoff_id},
                    },
                }
            )
            websocket.send_json({"event": "media", "media": {"payload": "caller-audio"}})
            audio_event = websocket.receive_json()
            assert audio_event == {
                "event": "media",
                "streamSid": "MZ124",
                "media": {"payload": "assistant-audio"},
            }
            websocket.send_json({"event": "stop"})

        assert fake_connection.sent_messages[0]["type"] == "session.update"
        assert fake_connection.sent_messages[1] == {
            "type": "input_audio_buffer.append",
            "audio": "caller-audio",
        }
        assert fake_connection.closed is True
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = original_connector


def test_voice_media_websocket_relays_audio_during_continuous_caller_frames() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_connector = voice_routes.twilio_media_bridge.openai_realtime_adapter.connector
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    fake_connection = DelayedAfterManyFramesRealtimeConnection(append_count_before_audio=3)

    async def fake_connector(_url, _headers):
        return fake_connection

    voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = fake_connector
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

        with client.websocket_connect("/api/voice/media") as websocket:
            websocket.send_json(
                {
                    "event": "start",
                    "start": {
                        "streamSid": "MZCONT",
                        "callSid": call_sid,
                        "customParameters": {"handoff_id": handoff_id},
                    },
                }
            )
            websocket.send_json({"event": "media", "media": {"payload": "caller-audio-1"}})
            websocket.send_json({"event": "media", "media": {"payload": "caller-audio-2"}})
            websocket.send_json({"event": "media", "media": {"payload": "caller-audio-3"}})
            audio_event = websocket.receive_json()
            assert audio_event == {
                "event": "media",
                "streamSid": "MZCONT",
                "media": {"payload": "assistant-audio"},
            }
            websocket.send_json({"event": "stop"})

        assert fake_connection.sent_messages[0]["type"] == "session.update"
        assert fake_connection.sent_messages[1:] == [
            {"type": "input_audio_buffer.append", "audio": "caller-audio-1"},
            {"type": "input_audio_buffer.append", "audio": "caller-audio-2"},
            {"type": "input_audio_buffer.append", "audio": "caller-audio-3"},
        ]
        assert fake_connection.closed is True
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = original_connector


def test_voice_media_websocket_relays_audio_and_tracks_session() -> None:
    original_adapter = dependency_handoff_service.voice_adapter
    original_connector = voice_routes.twilio_media_bridge.openai_realtime_adapter.connector
    original_debug_greeting = voice_routes.twilio_media_bridge.settings.openai_realtime_debug_greeting
    dependency_handoff_service.voice_adapter = StubVoiceAdapter()
    fake_connection = FakeRealtimeConnection(
        queued_events=[
            {"type": "session.updated"},
            {"type": "response.output_audio.delta", "delta": "assistant-audio"},
        ]
    )

    async def fake_connector(_url, _headers):
        return fake_connection

    voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = fake_connector
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

        with client.websocket_connect("/api/voice/media") as websocket:
            websocket.send_json(
                {
                    "event": "start",
                    "start": {
                        "streamSid": "MZ123",
                        "callSid": call_sid,
                        "customParameters": {"handoff_id": handoff_id},
                    },
                }
            )
            audio_event = websocket.receive_json()
            assert audio_event == {
                "event": "media",
                "streamSid": "MZ123",
                "media": {"payload": "assistant-audio"},
            }
            websocket.send_json({"event": "media", "media": {"payload": "caller-audio"}})
            websocket.send_json({"event": "stop"})

        assert fake_connection.sent_messages[0]["type"] == "session.update"
        assert fake_connection.sent_messages[1] == {
            "type": "input_audio_buffer.append",
            "audio": "caller-audio",
        }
        assert fake_connection.closed is True
    finally:
        dependency_handoff_service.voice_adapter = original_adapter
        voice_routes.twilio_media_bridge.openai_realtime_adapter.connector = original_connector
