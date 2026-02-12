from fastapi import APIRouter, Depends
from pysequence_api.dependencies import verify_api_key
from pysequence_api.routes import pods, accounts, activity, transfers, health

health_router = health.router

router = APIRouter(prefix="/api", dependencies=[Depends(verify_api_key)])

router.include_router(pods.router)
router.include_router(accounts.router)
router.include_router(activity.router)
router.include_router(transfers.router)
