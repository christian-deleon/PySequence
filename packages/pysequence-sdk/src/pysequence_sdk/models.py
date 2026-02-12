from pydantic import BaseModel


class Pod(BaseModel):
    id: str
    name: str
    organization_id: str
    balance_cents: int
    balance: str


class Port(BaseModel):
    id: str
    name: str
    organization_id: str
    balance_cents: int
    balance: str


class ExternalAccount(BaseModel):
    id: str
    name: str
    organization_id: str
    balance_cents: int
    balance: str


class TotalBalance(BaseModel):
    total_balance_cents: int
    total_balance: str
    pod_count: int


class TransferParty(BaseModel):
    name: str


class Transfer(BaseModel):
    id: str
    status: str
    amount: str
    amount_cents: int
    source: TransferParty
    destination: TransferParty
    direction: str
    activity_type: str
    created_at: str | None = None


class PageInfo(BaseModel):
    end_cursor: str
    has_next_page: bool


class ActivityPage(BaseModel):
    transfers: list[Transfer]
    page_info: PageInfo


class ActivitySummary(BaseModel):
    transfer_count: int
    rule_executions: int
    total_incoming_cents: int
    total_incoming: str


class AllAccounts(BaseModel):
    pods: list[Pod]
    ports: list[Port]
    accounts: list[ExternalAccount]
