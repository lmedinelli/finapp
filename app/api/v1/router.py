from fastapi import APIRouter

from app.api.router import router as base_router

router = APIRouter(prefix="/v1")
router.include_router(base_router)
