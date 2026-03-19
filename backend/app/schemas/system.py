from pydantic import BaseModel

from app.schemas.practice_info import OfficeAddressResponse, OfficeHoursResponse
from app.schemas.refill import RefillRequestResponse


class SystemConfigStatusResponse(BaseModel):
    app_name: str
    environment: str
    api_prefix: str
    openai_configured: bool
    openai_realtime_model: str
    openai_voice_name: str
    openai_realtime_debug_greeting: bool
    openai_realtime_transport: str
    openai_sip_configured: bool
    openai_webhook_configured: bool
    twilio_configured: bool
    twilio_webhook_base_url_configured: bool


class SystemOfficeHoursResponse(OfficeHoursResponse):
    pass


class SystemOfficeAddressResponse(OfficeAddressResponse):
    pass


class SystemRefillRequestResponse(RefillRequestResponse):
    pass
