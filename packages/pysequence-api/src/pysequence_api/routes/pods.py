from fastapi import APIRouter, Depends, HTTPException, Request
from pysequence_api.dependencies import get_client
from pysequence_sdk import SequenceClient

router = APIRouter()


@router.get("/pods")
def list_pods(client: SequenceClient = Depends(get_client)) -> list:
    return client.get_pods()


@router.get("/pods/balance")
def total_balance(client: SequenceClient = Depends(get_client)) -> dict:
    return client.get_total_balance()


@router.get("/pods/{pod_name}/balance")
def pod_balance(pod_name: str, client: SequenceClient = Depends(get_client)) -> dict:
    result = client.get_pod_balance(pod_name)

    if result is None:
        raise HTTPException(status_code=404, detail=f"Pod '{pod_name}' not found")

    return result


@router.get("/pods/detail/{pod_id}")
def pod_detail_by_id(
    pod_id: str,
    request: Request,
    client: SequenceClient = Depends(get_client),
) -> dict:
    org_id = request.app.state.server_config.org_id

    return client.get_pod_detail(org_id, pod_id)


@router.get("/pods/{org_id}/{pod_id}")
def pod_detail(
    org_id: str, pod_id: str, client: SequenceClient = Depends(get_client)
) -> dict:
    return client.get_pod_detail(org_id, pod_id)
