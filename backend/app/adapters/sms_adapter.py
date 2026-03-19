from app.core.config import Settings, get_settings
from app.schemas.notification import NotificationResult, SmsConfirmationPayload, SmsOptInPayload


class SmsAdapter:
    """Wraps outbound SMS delivery."""

    def __init__(self, client=None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client

    def _ensure_client(self):
        if self.client is not None:
            return self.client

        if not self.settings.twilio_configured:
            return None

        try:
            from twilio.rest import Client
        except ImportError as exc:
            raise RuntimeError("The Twilio SDK is required for live SMS delivery.") from exc

        self.client = Client(
            self.settings.twilio_account_sid,
            self.settings.twilio_auth_token,
        )
        return self.client

    def _format_appointment_time(self, value) -> str:
        formatted = value.strftime("%A, %b %d at %I:%M %p")
        return formatted.replace(" 0", " ").replace(" at 0", " at ")

    def _normalize_phone_number(self, recipient_phone_number: str) -> str:
        digits = "".join(character for character in recipient_phone_number if character.isdigit())
        if recipient_phone_number.startswith("+"):
            return recipient_phone_number
        if len(digits) == 10:
            return f"+1{digits}"
        if len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        return recipient_phone_number

    def _send_sms(self, recipient_phone_number: str, body: str) -> NotificationResult:
        normalized_phone_number = self._normalize_phone_number(recipient_phone_number)
        client = self._ensure_client()
        if client is None:
            return NotificationResult(
                channel="sms",
                delivered=True,
                detail=f"Stub SMS confirmation queued for {normalized_phone_number}.",
            )

        message = client.messages.create(
            to=normalized_phone_number,
            from_=self.settings.twilio_phone_number,
            body=body,
        )
        message_sid = getattr(message, "sid", None)
        kwargs = {
            "channel": "sms",
            "delivered": True,
            "detail": f"SMS sent to {normalized_phone_number} from {self.settings.twilio_phone_number}.",
        }
        if message_sid:
            kwargs["message_id"] = message_sid
        return NotificationResult(**kwargs)

    def send_booking_confirmation(self, payload: SmsConfirmationPayload) -> NotificationResult:
        appointment_time = self._format_appointment_time(payload.appointment_start)
        body = (
            f"Kyron Medical: Hi {payload.patient_name}, your appointment with {payload.provider_name} "
            f"is booked for {appointment_time}. Reply STOP to opt out of texts."
        )
        return self._send_sms(payload.recipient_phone_number, body)

    def send_opt_in_confirmation(self, payload: SmsOptInPayload) -> NotificationResult:
        body = (
            f"Kyron Medical: Hi {payload.patient_name}, you are signed up for text updates about your scheduling request. "
            "We will message this number with appointment updates. Reply STOP to opt out."
        )
        return self._send_sms(payload.recipient_phone_number, body)
