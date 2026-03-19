from pydantic import BaseModel


class Provider(BaseModel):
    id: str
    name: str
    specialty: str
    body_part_focus: str
    supported_terms: list[str]
