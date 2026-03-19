from app.core.config import get_settings


def test_settings_load_openai_api_key() -> None:
    settings = get_settings()

    assert settings.openai_api_key
    assert settings.api_prefix == "/api"
    assert settings.openai_configured is True
    assert settings.openai_realtime_model
    assert settings.openai_voice_name
    assert settings.twilio_account_sid
    assert settings.twilio_auth_token
    assert settings.twilio_phone_number
    assert settings.twilio_configured is True
    assert isinstance(settings.openai_webhook_configured, bool)


def test_settings_default_voice_transport_is_sip() -> None:
    settings = get_settings()

    assert settings.openai_realtime_transport == "sip"
