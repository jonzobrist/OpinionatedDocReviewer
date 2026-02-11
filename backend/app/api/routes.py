from fastapi import APIRouter
from app.api.comments import router as comments_router
from app.api.documents import router as documents_router
from app.api.persona_groups import router as persona_groups_router
from app.api.personas import router as personas_router
from app.api.review_jobs import router as review_jobs_router
from app.api.status import router as status_router
from app.api.settings import router as settings_router

api_router = APIRouter()

api_router.include_router(personas_router)
api_router.include_router(persona_groups_router)
api_router.include_router(documents_router)
api_router.include_router(comments_router)
api_router.include_router(review_jobs_router)
api_router.include_router(status_router)
api_router.include_router(settings_router)

@api_router.get("/health")
def health() -> dict:
    return {"status": "ok"}
