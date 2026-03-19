import re
from collections import defaultdict

from app.core.data_loader import load_providers
from app.schemas.provider_match import ProviderMatchResult


class ProviderMatchingService:
    """Matches patient concerns to supported providers."""

    def __init__(self) -> None:
        self.providers = load_providers()

    def match_concern(self, concern: str) -> ProviderMatchResult:
        normalized_concern = self._normalize(concern)
        provider_matches: dict[str, list[str]] = defaultdict(list)

        for provider in self.providers:
            for supported_term in provider.supported_terms:
                normalized_term = self._normalize(supported_term)
                if normalized_term and normalized_term in normalized_concern:
                    provider_matches[provider.id].append(supported_term)

        if not provider_matches:
            return ProviderMatchResult(
                matched=False,
                reason="The practice does not currently support that body part or concern.",
            )

        best_provider = next(
            provider
            for provider in self.providers
            if len(set(provider_matches.get(provider.id, [])))
            == max(len(set(matches)) for matches in provider_matches.values())
        )
        matched_terms = sorted(set(provider_matches[best_provider.id]))

        return ProviderMatchResult(
            matched=True,
            provider_id=best_provider.id,
            provider_name=best_provider.name,
            specialty=best_provider.specialty,
            matched_terms=matched_terms,
            reason="Matched using supported body-part and symptom terms.",
        )

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower())
        normalized = re.sub(r"\s+", " ", normalized)
        return f" {normalized.strip()} "
