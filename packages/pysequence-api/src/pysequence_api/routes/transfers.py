from fastapi import APIRouter, Depends, HTTPException, Request
from pysequence_api.dependencies import get_client
from pysequence_api.models import TransferRequest
from pysequence_sdk import SequenceClient

router = APIRouter()


@router.get("/transfers/{transfer_id}")
def transfer_status(
    transfer_id: str,
    request: Request,
    client: SequenceClient = Depends(get_client),
) -> dict:
    org_id = request.app.state.server_config.org_id

    return client.get_transfer_detail(org_id, transfer_id)


@router.post("/transfers")
def create_transfer(
    body: TransferRequest,
    request: Request,
    client: SequenceClient = Depends(get_client),
) -> dict:
    config = request.app.state.server_config
    daily_limits = request.app.state.daily_limits
    audit = request.app.state.audit

    # Per-transfer limit
    if body.amount_cents > config.max_transfer_cents:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Amount {body.amount_cents} cents exceeds per-transfer limit "
                f"of {config.max_transfer_cents} cents"
            ),
        )

    # Daily limit
    allowed, remaining = daily_limits.check(body.amount_cents)
    if not allowed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Amount {body.amount_cents} cents exceeds daily remaining limit "
                f"of {remaining} cents"
            ),
        )

    kyc_id = body.kyc_id or config.kyc_id

    audit.log(
        "transfer_requested",
        amount_cents=body.amount_cents,
        source=body.source_id,
        destination=body.destination_id,
    )

    try:
        result = client.transfer(
            kyc_id=kyc_id,
            source_id=body.source_id,
            destination_id=body.destination_id,
            amount_cents=body.amount_cents,
            source_type=body.source_type,
            destination_type=body.destination_type,
            description=body.description,
            instant=body.instant,
        )

    except RuntimeError as exc:
        error_msg = str(exc)

        audit.log(
            "transfer_failed",
            amount_cents=body.amount_cents,
            source=body.source_id,
            destination=body.destination_id,
            error=error_msg,
        )

        if "Transfer failed:" in error_msg:
            raise HTTPException(status_code=400, detail=error_msg)

        raise

    transfer_id = result.get("id", "unknown")
    daily_limits.record(body.amount_cents, transfer_id)

    audit.log(
        "transfer_completed",
        transfer_id=transfer_id,
        amount_cents=body.amount_cents,
        source=body.source_id,
        destination=body.destination_id,
    )

    return result
