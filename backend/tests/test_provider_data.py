from app.core.data_loader import load_providers


def test_provider_fixture_has_required_coverage() -> None:
    providers = load_providers()

    assert len(providers) >= 4
    assert len({provider.specialty for provider in providers}) >= 4

    for provider in providers:
        assert provider.supported_terms
        assert provider.body_part_focus
        assert provider.name.startswith("Dr.")
