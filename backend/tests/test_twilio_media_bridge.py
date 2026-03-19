from types import SimpleNamespace

from app.schemas.voice import OutboundCallResult
from app.services.conversation_service import ConversationService
from app.services.handoff_service import HandoffService
from app.services.realtime_voice_service import RealtimeVoiceService
from app.services.scheduling_service import SchedulingService
from app.services.twilio_media_bridge import TwilioMediaBridge


class StubVoiceAdapter:
    def create_outbound_call(self, handoff_id: str, to_number: str) -> OutboundCallResult:
        return OutboundCallResult(
            call_sid=f"CA{handoff_id[:8]}",
            status="queued",
            to_number=to_number,
            from_number="+18663565614",
        )


class StubOpenAIRealtimeAdapter:
    def build_session_update(self, session):
        return {"type": "session.update", "session": {"voice": session.voice}}

    def build_response_create(self):
        return {"type": "response.create"}

    def build_audio_append(self, payload: str):
        return {"type": "input_audio_buffer.append", "audio": payload}

    def build_audio_commit(self):
        return {"type": "input_audio_buffer.commit"}

    def build_twilio_media_event(self, stream_sid: str, audio_payload: str):
        return {"event": "media", "streamSid": stream_sid, "media": {"payload": audio_payload}}


def build_bridge():
    conversation_service = ConversationService()
    handoff_service = HandoffService(
        conversation_service=conversation_service,
        scheduling_service=SchedulingService(),
        voice_adapter=StubVoiceAdapter(),
    )
    realtime_voice_service = RealtimeVoiceService(
        handoff_service=handoff_service,
        settings=SimpleNamespace(
            openai_realtime_model="gpt-4o-realtime-preview",
            openai_voice_name="alloy",
        ),
    )
    bridge = TwilioMediaBridge(
        realtime_voice_service=realtime_voice_service,
        openai_realtime_adapter=StubOpenAIRealtimeAdapter(),
        settings=SimpleNamespace(twilio_webhook_base_url="https://example.ngrok-free.app"),
    )
    return conversation_service, handoff_service, bridge


def test_build_twiml_response_uses_media_stream() -> None:
    _, _, bridge = build_bridge()

    twiml = bridge.build_twiml_response("handoff-123")

    assert "<Connect><Stream" in twiml
    assert 'url="wss://example.ngrok-free.app/api/voice/media"' in twiml
    assert '<Parameter name="handoff_id" value="handoff-123" />' in twiml


def test_extract_handoff_id_reads_custom_parameters() -> None:
    _, _, bridge = build_bridge()

    handoff_id = bridge.extract_handoff_id(
        {
            "event": "start",
            "start": {"customParameters": {"handoff_id": "handoff-123"}},
        }
    )

    assert handoff_id == "handoff-123"


def test_extract_handoff_id_reads_parameter_list_shape() -> None:
    _, _, bridge = build_bridge()

    handoff_id = bridge.extract_handoff_id(
        {
            "event": "start",
            "start": {
                "parameters": [
                    {"name": "handoff_id", "value": "handoff-123"},
                ]
            },
        }
    )

    assert handoff_id == "handoff-123"


def test_handle_start_event_builds_realtime_session_and_tracks_stream() -> None:
    conversation_service, handoff_service, bridge = build_bridge()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(conversation.id, first_name="Taylor", phone_number="555-123-4567")
    handoff = handoff_service.create_handoff(conversation.id)

    result = bridge.handle_stream_event(
        handoff.handoff_id,
        {
            "event": "start",
            "start": {"streamSid": "MZ123", "callSid": handoff.call_sid},
        },
    )

    assert result["handled"] is True
    assert result["event"] == "start"
    assert result["stream_sid"] == "MZ123"
    assert result["session"]["conversation_id"] == conversation.id
    assert result["openai_events"][0]["type"] == "session.update"
    assert result["openai_events"][1]["type"] == "response.create"
    context = handoff_service.get_handoff_context(handoff.handoff_id)
    assert context.stream_sid == "MZ123"
    assert context.realtime_session_status == "connected"


def test_handle_media_event_translates_audio_for_openai() -> None:
    _, _, bridge = build_bridge()

    result = bridge.handle_stream_event(
        "handoff-123",
        {
            "event": "media",
            "media": {"payload": "abc123"},
        },
    )

    assert result == {
        "handled": True,
        "event": "media",
        "openai_event": {"type": "input_audio_buffer.append", "audio": "abc123"},
    }


def test_handle_transcript_event_appends_to_conversation() -> None:
    conversation_service, handoff_service, bridge = build_bridge()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(conversation.id, first_name="Taylor", phone_number="555-123-4567")
    handoff = handoff_service.create_handoff(conversation.id)

    bridge.handle_stream_event(
        handoff.handoff_id,
        {
            "event": "transcript",
            "transcript": {"role": "user", "content": "I need the earliest time available"},
        },
    )

    updated = conversation_service.get_conversation(conversation.id)
    assert updated.messages[-1].content == "I need the earliest time available"


def test_handle_openai_audio_event_translates_audio_for_twilio() -> None:
    conversation_service, handoff_service, bridge = build_bridge()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(conversation.id, first_name="Taylor", phone_number="555-123-4567")
    handoff = handoff_service.create_handoff(conversation.id)
    bridge.handle_stream_event(
        handoff.handoff_id,
        {
            "event": "start",
            "start": {"streamSid": "MZ123", "callSid": handoff.call_sid},
        },
    )

    result = bridge.handle_openai_server_event(
        handoff.handoff_id,
        {
            "type": "response.output_audio.delta",
            "delta": "assistant-audio",
        },
    )

    assert result == [
        {
            "event": "media",
            "streamSid": "MZ123",
            "media": {"payload": "assistant-audio"},
        }
    ]


def test_handle_stop_event_marks_session_completed() -> None:
    conversation_service, handoff_service, bridge = build_bridge()
    conversation = conversation_service.create_conversation()
    conversation_service.update_intake(conversation.id, first_name="Taylor", phone_number="555-123-4567")
    handoff = handoff_service.create_handoff(conversation.id)

    result = bridge.handle_stream_event(handoff.handoff_id, {"event": "stop"})

    assert result == {
        "handled": True,
        "event": "stop",
        "openai_event": {"type": "input_audio_buffer.commit"},
    }
    assert handoff_service.get_handoff_context(handoff.handoff_id).realtime_session_status == "completed"
