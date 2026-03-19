from app.services.refill_service import RefillService


def test_refill_service_returns_safe_stubbed_request_response() -> None:
    service = RefillService()

    response = service.create_request_response("Need a refill for my inhaler")

    assert response.workflow_type == "refill_request"
    assert "cannot verify live refill status" in response.assistant_message
    assert "Need a refill for my inhaler" in response.assistant_message
    assert "staff member would follow up" in response.assistant_message
