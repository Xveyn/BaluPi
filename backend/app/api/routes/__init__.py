"""API route registration."""

from fastapi import APIRouter

from app.api.routes import health, system, auth, energy, tapo, nas, handshake, snapshot

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(energy.router, prefix="/energy", tags=["energy"])
api_router.include_router(tapo.router, prefix="/tapo", tags=["tapo"])
api_router.include_router(nas.router, prefix="/nas", tags=["nas"])
api_router.include_router(handshake.router, prefix="/handshake", tags=["handshake"])
api_router.include_router(snapshot.router, prefix="/handshake", tags=["handshake"])
