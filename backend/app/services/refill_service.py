from app.schemas.refill import RefillRequestResponse


class RefillService:
    def create_request_response(self, message: str) -> RefillRequestResponse:
        normalized_message = " ".join(message.strip().split())

        assistant_message = (
            "I can help start a prescription refill request, but I cannot verify live refill status or "
            "provide medication advice here. I have noted your refill request"
        )
        if normalized_message:
            assistant_message += f" for: {normalized_message}."
        else:
            assistant_message += "."
        assistant_message += " A staff member would follow up using the contact information on file."

        return RefillRequestResponse(
            assistant_message=assistant_message,
            workflow_type="refill_request",
        )
