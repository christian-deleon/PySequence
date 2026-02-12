import secrets

from fastapi import Header, HTTPException, Request
from pysequence_sdk import SequenceClient


def get_client(request: Request) -> SequenceClient:
    return request.app.state.client


def verify_api_key(request: Request, x_api_key: str = Header()) -> None:
    if not secrets.compare_digest(x_api_key, request.app.state.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
