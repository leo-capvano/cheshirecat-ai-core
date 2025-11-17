from fastapi import APIRouter
from .oauth import router as oauth_router
from .default_idp.idp import router as idp_router

router = APIRouter(prefix="/auth", tags=["Auth"])
for r in [oauth_router, idp_router]:
    router.include_router(r)