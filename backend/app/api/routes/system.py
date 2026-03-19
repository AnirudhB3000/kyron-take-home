from fastapi import APIRouter

from app.core.config import get_settings
from app.core.dependencies import practice_info_service, refill_service
from app.schemas.refill import RefillRequestPayload
from app.schemas.system import (
    SystemConfigStatusResponse,
    SystemOfficeAddressResponse,
    SystemOfficeHoursResponse,
    SystemRefillRequestResponse,
)

router = APIRouter()


@router.get("/config-status", response_model=SystemConfigStatusResponse)
def config_status() -> SystemConfigStatusResponse:
    settings = get_settings()
    return SystemConfigStatusResponse(
        app_name=settings.app_name,
        environment=settings.environment,
        api_prefix=settings.api_prefix,
        openai_configured=settings.openai_configured,
        openai_realtime_model=settings.openai_realtime_model,
        openai_voice_name=settings.openai_voice_name,
        openai_realtime_debug_greeting=settings.openai_realtime_debug_greeting,
        openai_realtime_transport=settings.openai_realtime_transport,
        openai_sip_configured=settings.openai_sip_configured,
        openai_webhook_configured=settings.openai_webhook_configured,
        twilio_configured=settings.twilio_configured,
        twilio_webhook_base_url_configured=bool(settings.twilio_webhook_base_url),
    )


@router.get("/office-hours", response_model=SystemOfficeHoursResponse)
def office_hours() -> SystemOfficeHoursResponse:
    return SystemOfficeHoursResponse(**practice_info_service.get_office_hours().model_dump())


@router.get("/office-address", response_model=SystemOfficeAddressResponse)
def office_address() -> SystemOfficeAddressResponse:
    return SystemOfficeAddressResponse(**practice_info_service.get_office_address().model_dump())


@router.post("/refill-request", response_model=SystemRefillRequestResponse)
def refill_request(payload: RefillRequestPayload) -> SystemRefillRequestResponse:
    return SystemRefillRequestResponse(**refill_service.create_request_response(payload.message).model_dump())
