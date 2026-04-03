from fastapi import APIRouter

from app.api.routes.agent import router as agent_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.memory import router as memory_router
from app.api.routes.patients import router as patients_router

router = APIRouter()
router.include_router(agent_router)
router.include_router(memory_router)
router.include_router(patients_router)
router.include_router(dashboard_router)
