from app.adapters.email_adapter import EmailAdapter
from app.adapters.sms_adapter import SmsAdapter
from app.schemas.notification import (
    BookingNotifications,
    EmailConfirmationPayload,
    NotificationResult,
    SmsConfirmationPayload,
    SmsOptInPayload,
)
from app.schemas.scheduling import AppointmentSlot


class NotificationService:
    def __init__(
        self,
        email_adapter: EmailAdapter | None = None,
        sms_adapter: SmsAdapter | None = None,
    ) -> None:
        self.email_adapter = email_adapter or EmailAdapter()
        self.sms_adapter = sms_adapter or SmsAdapter()

    def send_sms_opt_in_confirmation(
        self,
        conversation_id: str,
        patient_first_name: str,
        patient_last_name: str,
        patient_phone_number: str,
    ) -> NotificationResult:
        patient_name = f"{patient_first_name} {patient_last_name}".strip() or "there"
        return NotificationResult.model_validate(
            self.sms_adapter.send_opt_in_confirmation(
                SmsOptInPayload(
                    conversation_id=conversation_id,
                    recipient_phone_number=patient_phone_number,
                    patient_name=patient_name,
                )
            )
        )

    def send_booking_confirmations(
        self,
        conversation_id: str,
        patient_first_name: str,
        patient_last_name: str,
        patient_email: str,
        patient_phone_number: str,
        sms_opt_in: bool,
        provider_name: str,
        specialty: str,
        slot: AppointmentSlot,
    ) -> BookingNotifications:
        patient_name = f"{patient_first_name} {patient_last_name}".strip()
        email_result = self.email_adapter.send_booking_confirmation(
            EmailConfirmationPayload(
                conversation_id=conversation_id,
                recipient_email=patient_email,
                patient_name=patient_name,
                provider_name=provider_name,
                specialty=specialty,
                appointment_start=slot.start_at,
                appointment_end=slot.end_at,
            )
        )

        sms_result = None
        if sms_opt_in:
            sms_result = self.sms_adapter.send_booking_confirmation(
                SmsConfirmationPayload(
                    conversation_id=conversation_id,
                    recipient_phone_number=patient_phone_number,
                    patient_name=patient_name,
                    provider_name=provider_name,
                    appointment_start=slot.start_at,
                )
            )

        return BookingNotifications(email=email_result, sms=sms_result)
