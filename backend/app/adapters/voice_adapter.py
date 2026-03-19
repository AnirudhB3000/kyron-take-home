import logging
from urllib.parse import urlencode

from app.core.config import Settings, get_settings
from app.schemas.voice import OutboundCallResult


logger = logging.getLogger(__name__)


def _emit_voice_adapter_trace(message: str) -> None:
    print(message, flush=True)
    logger.info(message)


class VoiceAdapter:
    """Wraps Twilio voice integration for outbound calls."""

    def __init__(self, client=None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client

    def _ensure_client(self):
        if self.client is not None:
            return self.client

        if not self.settings.twilio_configured:
            raise ValueError("Twilio calling is not configured yet.")

        try:
            from twilio.rest import Client
        except ImportError as exc:
            raise RuntimeError("The Twilio SDK is required for live outbound calling.") from exc

        self.client = Client(
            self.settings.twilio_account_sid,
            self.settings.twilio_auth_token,
        )
        return self.client

    def create_outbound_call(self, handoff_id: str, to_number: str) -> OutboundCallResult:
        if not self.settings.twilio_configured:
            raise ValueError("Twilio calling is not configured yet.")
        if not self.settings.twilio_webhook_base_url:
            raise ValueError("TWILIO_WEBHOOK_BASE_URL is required for live outbound calling.")

        client = self._ensure_client()
        query = urlencode({"handoff_id": handoff_id})
        base_url = self.settings.twilio_webhook_base_url.rstrip("/")
        twiml_url = f"{base_url}/api/voice/twiml?{query}"
        status_url = f"{base_url}/api/voice/status?{query}"
        _emit_voice_adapter_trace(
            f"Voice adapter: creating outbound call handoff_id={handoff_id} to_number={to_number} twiml_url={twiml_url} status_callback_url={status_url}"
        )
        call = client.calls.create(
            to=to_number,
            from_=self.settings.twilio_phone_number,
            url=twiml_url,
            status_callback=status_url,
            status_callback_method="POST",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
        )
        result = OutboundCallResult(
            call_sid=call.sid,
            status=getattr(call, "status", "queued"),
            to_number=to_number,
            from_number=self.settings.twilio_phone_number or "",
            twiml_url=twiml_url,
            status_callback_url=status_url,
        )
        _emit_voice_adapter_trace(
            f"Voice adapter: outbound call created handoff_id={handoff_id} call_sid={result.call_sid} status={result.status}"
        )
        return result
