from fastapi import APIRouter, WebSocket

from app.api.routes.health import router as health_router
from app.api.routes.scheduling import router as scheduling_router
from app.api.routes.system import router as system_router
from app.api.routes.voice import router as voice_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(system_router, prefix="/system", tags=["system"])
api_router.include_router(scheduling_router, prefix="/scheduling", tags=["scheduling"])
api_router.include_router(voice_router, prefix="/voice", tags=["voice"])
