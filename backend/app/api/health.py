from fastapi import APIRouter

from app.core.response import ResponseModel

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> ResponseModel[dict[str, str]]:
    return ResponseModel.ok({"status": "ok", "version": "0.1.0"})
