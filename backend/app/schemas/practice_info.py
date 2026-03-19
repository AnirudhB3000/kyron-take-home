from pydantic import BaseModel


class OfficeHoursResponse(BaseModel):
    weekdays: list[str]
    saturday: str
    sunday: str


class OfficeAddressResponse(BaseModel):
    practice_name: str
    street: str
    city: str
    state: str
    postal_code: str
    phone_number: str
