from app.schemas.practice_info import OfficeAddressResponse, OfficeHoursResponse


class PracticeInfoService:
    def get_office_hours(self) -> OfficeHoursResponse:
        return OfficeHoursResponse(
            weekdays=[
                "Monday to Thursday: 8:00 AM to 5:30 PM",
                "Friday: 8:00 AM to 4:00 PM",
            ],
            saturday="Saturday: Urgent scheduling callbacks only from 9:00 AM to 12:00 PM",
            sunday="Sunday: Closed",
        )

    def get_office_address(self) -> OfficeAddressResponse:
        return OfficeAddressResponse(
            practice_name="Kyron Medical Downtown Clinic",
            street="1450 Market Street, Suite 600",
            city="San Francisco",
            state="CA",
            postal_code="94103",
            phone_number="(415) 555-0112",
        )
