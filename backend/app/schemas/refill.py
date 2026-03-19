from pydantic import BaseModel


class RefillRequestPayload(BaseModel):
    message: str


class RefillRequestResponse(BaseModel):
    assistant_message: str
    workflow_type: str
