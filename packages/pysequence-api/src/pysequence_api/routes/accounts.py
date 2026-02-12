from fastapi import APIRouter, Depends, Request
from pysequence_api.dependencies import get_client
from pysequence_sdk import SequenceClient

router = APIRouter()


@router.get("/accounts")
def list_accounts(
    request: Request,
    org_id: str | None = None,
    client: SequenceClient = Depends(get_client),
) -> dict:
    resolved_org_id = org_id or request.app.state.server_config.org_id or None

    return client.get_all_accounts(org_id=resolved_org_id)
