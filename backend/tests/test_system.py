import logging

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_config_status_hides_secret_values() -> None:
    response = client.get("/api/system/config-status")

    assert response.status_code == 200

    payload = response.json()

    assert payload["app_name"] == "Kyron Take Home API"
    assert payload["environment"] == "development"
    assert payload["api_prefix"] == "/api"
    assert payload["openai_configured"] is True
    assert payload["openai_realtime_model"]
    assert payload["openai_voice_name"]
    assert isinstance(payload["openai_realtime_debug_greeting"], bool)
    assert payload["openai_realtime_transport"] == "sip"
    assert isinstance(payload["openai_sip_configured"], bool)
    assert isinstance(payload["openai_webhook_configured"], bool)
    assert payload["twilio_configured"] is True
    assert payload["twilio_webhook_base_url_configured"] is True
    assert "openai_api_key" not in payload
    assert "twilio_auth_token" not in payload


def test_office_hours_endpoint_returns_structured_hours() -> None:
    response = client.get("/api/system/office-hours")

    assert response.status_code == 200
    payload = response.json()
    assert payload["weekdays"]
    assert "Monday" in payload["weekdays"][0]
    assert "Sunday" in payload["sunday"]


def test_office_address_endpoint_returns_structured_address() -> None:
    response = client.get("/api/system/office-address")

    assert response.status_code == 200
    payload = response.json()
    assert payload["practice_name"] == "Kyron Medical Downtown Clinic"
    assert payload["city"] == "San Francisco"
    assert payload["phone_number"] == "(415) 555-0112"


def test_refill_request_endpoint_returns_stubbed_request_intake_response() -> None:
    response = client.post(
        "/api/system/refill-request",
        json={"message": "I need a refill for my blood pressure medication"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_type"] == "refill_request"
    assert "cannot verify live refill status" in payload["assistant_message"]
    assert "staff member would follow up" in payload["assistant_message"]


def test_app_configures_root_logging_for_info_traces() -> None:
    assert logging.getLogger().isEnabledFor(logging.INFO)


def test_cors_allows_deployed_vercel_origin() -> None:
    response = client.options(
        "/api/health",
        headers={
            "Origin": "https://kyron-take-home-git-main-anirudhb3000s-projects.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://kyron-take-home-git-main-anirudhb3000s-projects.vercel.app"
    )
