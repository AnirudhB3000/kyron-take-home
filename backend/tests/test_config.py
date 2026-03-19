from app.core.config import Settings, get_settings


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


def test_settings_default_cors_origins_include_localhosts() -> None:
    settings = Settings(openai_api_key="test-key", _env_file=None)

    assert settings.cors_allowed_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_settings_default_cors_origin_regex_allows_project_vercel_deployments() -> None:
    settings = Settings(openai_api_key="test-key", _env_file=None)

    assert (
        settings.cors_allowed_origin_regex
        == r"^https://kyron-take-home(?:-[a-z0-9-]+)?-anirudhb3000s-projects\.vercel\.app$"
    )


def test_settings_merge_additional_frontend_origins_from_env_var() -> None:
    settings = Settings(
        openai_api_key="test-key",
        frontend_origins="https://kyron-take-home.vercel.app/, https://demo.kyron.example",
        _env_file=None,
    )

    assert settings.cors_allowed_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://kyron-take-home.vercel.app",
        "https://demo.kyron.example",
    ]
