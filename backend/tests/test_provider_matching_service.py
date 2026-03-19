from app.services.provider_matching_service import ProviderMatchingService


service = ProviderMatchingService()


def test_matches_orthopedics_for_knee_concern() -> None:
    result = service.match_concern("I need help with my knee pain.")

    assert result.matched is True
    assert result.specialty == "Orthopedics"
    assert "knee" in result.matched_terms


def test_matches_ophthalmology_for_blurry_vision() -> None:
    result = service.match_concern("I have blurry vision in my left eye.")

    assert result.matched is True
    assert result.specialty == "Ophthalmology"
    assert "blurry vision" in result.matched_terms


def test_matches_dermatology_for_scalp_rash() -> None:
    result = service.match_concern("I have a rash on my scalp that will not go away.")

    assert result.matched is True
    assert result.specialty == "Dermatology"
    assert "rash" in result.matched_terms
    assert "scalp" in result.matched_terms


def test_matches_orthopedics_for_multiple_joint_terms() -> None:
    result = service.match_concern("My shoulder and knee hurt after a sports injury.")

    assert result.matched is True
    assert result.specialty == "Orthopedics"
    assert "knee" in result.matched_terms
    assert "shoulder" in result.matched_terms
    assert "sports injury" in result.matched_terms


def test_matches_ent_for_sinus_and_throat_concern() -> None:
    result = service.match_concern("I have sinus pressure and throat pain.")

    assert result.matched is True
    assert result.specialty == "ENT"
    assert "sinus" in result.matched_terms
    assert "throat" in result.matched_terms


def test_returns_unmatched_for_unsupported_body_part() -> None:
    result = service.match_concern("I need help with stomach pain.")

    assert result.matched is False
    assert result.provider_id is None
    assert result.specialty is None


def test_tie_breaking_stays_deterministic() -> None:
    result = service.match_concern("My eyes and skin are both irritated.")

    assert result.matched is True
    assert result.provider_name == "Dr. Marcus Chen"
