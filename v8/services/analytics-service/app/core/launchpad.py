from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.quantum_params import fetch_quantum_params
from app.persistence.vault import quantum_engine
from app.presentation.nexus_portals import wavelength_portal, vitality_portal


@asynccontextmanager
async def nexus_lifecycle(gateway: FastAPI):
    yield
    await quantum_engine.dispose()


nexus_gateway = FastAPI(
    title="Analytics Quantum Nexus",
    description="Unconventional stock wavelength analysis with fractal momentum",
    version="1.0.0",
    lifespan=nexus_lifecycle,
)

nexus_gateway.include_router(wavelength_portal)
nexus_gateway.include_router(vitality_portal)


@nexus_gateway.get("/")
async def nexus_root():
    return {
        "nexus": "Analytics Quantum Gateway",
        "wavelength_portals": ["/api/v1/analytics/trends"],
        "vitality_probe": "/health",
    }
