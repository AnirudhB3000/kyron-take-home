from types import SimpleNamespace

from app.adapters.openai_realtime_adapter import OpenAIRealtimeAdapter


def build_settings(**overrides):
    defaults = {
        "openai_api_key": "sk-test",
        "openai_realtime_model": "gpt-realtime",
        "openai_voice_name": "alloy",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_build_connect_url_uses_model() -> None:
    adapter = OpenAIRealtimeAdapter(settings=build_settings())

    assert adapter.build_connect_url() == "wss://api.openai.com/v1/realtime?model=gpt-realtime"


def test_build_session_update_uses_voice_and_instructions() -> None:
    adapter = OpenAIRealtimeAdapter(settings=build_settings())
    session = SimpleNamespace(
        voice="alloy",
        instructions="Continue the conversation safely.",
    )

    payload = adapter.build_session_update(session)

    assert payload["type"] == "session.update"
    assert payload["session"]["voice"] == "alloy"
    assert payload["session"]["instructions"] == "Continue the conversation safely."
    assert payload["session"]["turn_detection"] == {
        "type": "server_vad",
        "create_response": True,
        "interrupt_response": True,
        "silence_duration_ms": 500,
    }


def test_build_audio_append_wraps_payload() -> None:
    adapter = OpenAIRealtimeAdapter(settings=build_settings())

    assert adapter.build_audio_append("abc123") == {
        "type": "input_audio_buffer.append",
        "audio": "abc123",
    }
