from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
import asyncio

from app.core.vault_bridge import yield_vault_session
from app.core.blueprint import tower_blueprint
from app.logic.conduit_nexus import conduit_nexus_singleton
from app.logic.pulse_conductor import PulseConductor
from app.presentation.pulse_schemas import (
    EnrollmentRequest,
    EnrollmentManifest,
    TowerStatus
)


@asynccontextmanager
async def tower_lifecycle(application: FastAPI):
    """Manages tower startup and shutdown lifecycle"""
    yield


tower_instance = FastAPI(
    title="Beacon Transmission Tower",
    description="Multi-conduit beacon system for real-time pulse propagation",
    version="1.0.0",
    lifespan=tower_lifecycle
)


@tower_instance.get("/health", response_model=TowerStatus)
async def evaluate_tower_status():
    """Evaluate tower operational status"""
    nexus_metrics = conduit_nexus_singleton.compile_nexus_metrics()
    
    return TowerStatus(
        tower_designation="beacon-transmission-tower",
        is_operational=True,
        status_timestamp=datetime.now(timezone.utc).isoformat(),
        active_conduits=nexus_metrics["conduit_count"]
    )


@tower_instance.post(
    "/api/v1/notifications/subscribe",
    response_model=EnrollmentManifest,
    status_code=201
)
async def enroll_receptor_pathway(
    enrollment_request: EnrollmentRequest,
    vault_session: AsyncSession = Depends(yield_vault_session)
):
    """Enroll receptor to pathway and subject"""
    
    receptor_identity = "system_user"
    
    conductor = PulseConductor(vault_session)
    
    try:
        enrollment_manifest = await conductor.orchestrate_receptor_enrollment(
            receptor_id=receptor_identity,
            pathway_designation=enrollment_request.channel,
            subject_designation=enrollment_request.topic
        )
        
        return EnrollmentManifest(**enrollment_manifest)
    
    except Exception as enrollment_failure:
        raise HTTPException(
            status_code=500,
            detail=f"Enrollment orchestration failed: {str(enrollment_failure)}"
        )


@tower_instance.websocket("/ws/{user_id}")
async def conduit_stream_endpoint(
    conduit_wire: WebSocket,
    user_id: str
):
    """Conduit endpoint for real-time pulse streaming"""
    
    await conduit_nexus_singleton.establish_conduit(
        receptor_id=user_id,
        conduit_wire=conduit_wire
    )
    
    try:
        initiation_pulse = {
            "pulse_category": "conduit_established",
            "receptor_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "beacon_text": "Conduit wire activated for pulse reception"
        }
        await conduit_wire.send_json(initiation_pulse)
        
        heartbeat_cycle = tower_blueprint.conduit_heartbeat_cycle
        
        while True:
            try:
                incoming_signal = await asyncio.wait_for(
                    conduit_wire.receive_text(),
                    timeout=heartbeat_cycle
                )
                
                if incoming_signal == "ping":
                    await conduit_wire.send_text("pong")
            
            except asyncio.TimeoutError:
                vitality_pulse = {
                    "pulse_category": "vitality_check",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await conduit_wire.send_json(vitality_pulse)
    
    except WebSocketDisconnect:
        conduit_nexus_singleton.sever_conduit(user_id, conduit_wire)
    
    except Exception:
        conduit_nexus_singleton.sever_conduit(user_id, conduit_wire)
        raise
