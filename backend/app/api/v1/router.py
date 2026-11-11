from fastapi import APIRouter

from app.api.v1 import (
    auth, calc, children, files, health, mistakes, reports, rewards, stars, tasks,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(children.router)
api_router.include_router(files.router)
api_router.include_router(tasks.router)
api_router.include_router(mistakes.router)
api_router.include_router(calc.router)
api_router.include_router(stars.router)
api_router.include_router(rewards.router)
api_router.include_router(reports.router)
