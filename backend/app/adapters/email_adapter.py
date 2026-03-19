from app.schemas.notification import EmailConfirmationPayload, NotificationResult


class EmailAdapter:
    """Wraps outbound email delivery."""

    def send_booking_confirmation(self, payload: EmailConfirmationPayload) -> NotificationResult:
        return NotificationResult(
            channel="email",
            delivered=True,
            detail=f"Stub email confirmation queued for {payload.recipient_email}.",
        )
