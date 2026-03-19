from datetime import datetime

from app.services.notification_service import NotificationService
from app.services.scheduling_service import SchedulingService


class StubEmailAdapter:
    def __init__(self) -> None:
        self.payloads = []

    def send_booking_confirmation(self, payload):
        self.payloads.append(payload)
        return {
            "channel": "email",
            "delivered": True,
            "message_id": "email-1",
            "sent_at": datetime(2026, 3, 17, 12, 0, 0),
            "detail": "email queued",
        }


class StubSmsAdapter:
    def __init__(self) -> None:
        self.payloads = []

    def send_booking_confirmation(self, payload):
        self.payloads.append(("booking", payload))
        return {
            "channel": "sms",
            "delivered": True,
            "message_id": "sms-1",
            "sent_at": datetime(2026, 3, 17, 12, 0, 0),
            "detail": "sms queued",
        }

    def send_opt_in_confirmation(self, payload):
        self.payloads.append(("opt_in", payload))
        return {
            "channel": "sms",
            "delivered": True,
            "message_id": "sms-2",
            "sent_at": datetime(2026, 3, 17, 12, 5, 0),
            "detail": "sms opt-in queued",
        }


service = SchedulingService()
slot = service.list_slots("dr-olivia-bennett")[0]


def test_sends_email_confirmation_for_every_booking() -> None:
    email_adapter = StubEmailAdapter()
    sms_adapter = StubSmsAdapter()
    notification_service = NotificationService(
        email_adapter=email_adapter,
        sms_adapter=sms_adapter,
    )

    notifications = notification_service.send_booking_confirmations(
        conversation_id="conversation-1",
        patient_first_name="Taylor",
        patient_last_name="Morgan",
        patient_email="taylor@example.com",
        patient_phone_number="555-123-4567",
        sms_opt_in=False,
        provider_name="Dr. Olivia Bennett",
        specialty="Orthopedics",
        slot=slot,
    )

    assert notifications.email.channel == "email"
    assert notifications.email.delivered is True
    assert notifications.sms is None
    assert len(email_adapter.payloads) == 1
    assert len(sms_adapter.payloads) == 0


def test_sends_sms_only_when_patient_opted_in() -> None:
    email_adapter = StubEmailAdapter()
    sms_adapter = StubSmsAdapter()
    notification_service = NotificationService(
        email_adapter=email_adapter,
        sms_adapter=sms_adapter,
    )

    notifications = notification_service.send_booking_confirmations(
        conversation_id="conversation-2",
        patient_first_name="Taylor",
        patient_last_name="Morgan",
        patient_email="taylor@example.com",
        patient_phone_number="555-123-4567",
        sms_opt_in=True,
        provider_name="Dr. Olivia Bennett",
        specialty="Orthopedics",
        slot=slot,
    )

    assert notifications.email.channel == "email"
    assert notifications.sms is not None
    assert notifications.sms.channel == "sms"
    assert len(email_adapter.payloads) == 1
    assert len(sms_adapter.payloads) == 1


def test_sends_opt_in_confirmation_text() -> None:
    sms_adapter = StubSmsAdapter()
    notification_service = NotificationService(sms_adapter=sms_adapter)

    notification = notification_service.send_sms_opt_in_confirmation(
        conversation_id="conversation-3",
        patient_first_name="Taylor",
        patient_last_name="Morgan",
        patient_phone_number="555-123-4567",
    )

    assert notification.channel == "sms"
    assert notification.message_id == "sms-2"
    assert len(sms_adapter.payloads) == 1
    kind, payload = sms_adapter.payloads[0]
    assert kind == "opt_in"
    assert payload.recipient_phone_number == "555-123-4567"
