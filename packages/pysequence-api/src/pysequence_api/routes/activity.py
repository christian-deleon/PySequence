from fastapi import APIRouter, Depends, Request
from pysequence_api.dependencies import get_client
from pysequence_sdk import SequenceClient


router = APIRouter()


@router.get("/activity/summary")
def activity_summary(client: SequenceClient = Depends(get_client)) -> dict:
    return client.get_activity_summary()


@router.get("/activity")
def list_activity(
    request: Request,
    first: int = 10,
    after: str = "",
    org_id: str | None = None,
    statuses: str | None = None,
    directions: str | None = None,
    activity_types: str | None = None,
    client: SequenceClient = Depends(get_client),
) -> dict:
    resolved_org_id = org_id or request.app.state.server_config.org_id

    return client.get_activity(
        org_id=resolved_org_id,
        first=first,
        after=after,
        statuses=statuses.split(",") if statuses else None,
        directions=directions.split(",") if directions else None,
        activity_types=activity_types.split(",") if activity_types else None,
    )


@router.get("/activity/{org_id}/{transfer_id}")
def transfer_detail(
    org_id: str,
    transfer_id: str,
    client: SequenceClient = Depends(get_client),
) -> dict:
    return client.get_transfer_detail(org_id, transfer_id)
