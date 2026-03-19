from pydantic import BaseModel


class ProviderMatchResult(BaseModel):
    matched: bool
    provider_id: str | None = None
    provider_name: str | None = None
    specialty: str | None = None
    matched_terms: list[str] = []
    reason: str
