from datetime import datetime

from pydantic import BaseModel


class AvailabilitySlot(BaseModel):
    slot_id: str
    provider_id: str
    start_at: datetime
    end_at: datetime
    appointment_type: str
