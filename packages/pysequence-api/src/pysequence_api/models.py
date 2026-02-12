from pydantic import BaseModel, Field


class TransferRequest(BaseModel):
    kyc_id: str | None = None
    source_id: str
    destination_id: str
    amount_cents: int = Field(gt=0)
    source_type: str = "POD"
    destination_type: str = "POD"
    description: str = ""
    instant: bool = False
