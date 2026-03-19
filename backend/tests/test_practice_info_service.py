from app.services.practice_info_service import PracticeInfoService


service = PracticeInfoService()


def test_returns_structured_office_hours() -> None:
    hours = service.get_office_hours()

    assert hours.weekdays
    assert "Monday" in hours.weekdays[0]
    assert "Sunday" in hours.sunday


def test_returns_structured_office_address() -> None:
    address = service.get_office_address()

    assert address.practice_name == "Kyron Medical Downtown Clinic"
    assert address.city == "San Francisco"
    assert address.phone_number == "(415) 555-0112"
