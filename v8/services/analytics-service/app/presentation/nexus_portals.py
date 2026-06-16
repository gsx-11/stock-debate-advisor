from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime, timezone

from app.presentation.wavelength_schemas import (
    WavelengthInquiry,
    WavelengthRevelation,
    VitalityProbe,
    HarmonicPattern,
)
from app.persistence.vault import conjure_vault_session
from app.persistence.chronicle_entities import WaveformChronicle
from app.logic.fractal_momentum_weaver import FractalMomentumWeaver

wavelength_portal = APIRouter(prefix="/api/v1/analytics", tags=["wavelength_analysis"])
vitality_portal = APIRouter(tags=["vitality"])


@wavelength_portal.post("/trends", response_model=WavelengthRevelation)
async def analyze_wavelength_trends(
    inquiry: WavelengthInquiry,
    vault_session: AsyncSession = Depends(conjure_vault_session)
):
    try:
        momentum_weaver = FractalMomentumWeaver(
            ticker_sigil=inquiry.ticker_sigil,
            temporal_span=inquiry.temporal_span
        )
        
        analysis_synthesis = momentum_weaver.synthesize_wavelength_analysis()
        
        chronicle_record = WaveformChronicle(
            ticker_sigil=inquiry.ticker_sigil,
            wavelength_signature=analysis_synthesis["wavelength_signature"],
            harmonic_certainty=analysis_synthesis["harmonic_certainty"],
            temporal_anchor=analysis_synthesis["temporal_anchor"],
        )
        
        vault_session.add(chronicle_record)
        await vault_session.commit()
        await vault_session.refresh(chronicle_record)
        
        revelation = WavelengthRevelation(
            ticker_sigil=inquiry.ticker_sigil,
            wavelength_signature=analysis_synthesis["wavelength_signature"],
            harmonic_certainty=analysis_synthesis["harmonic_certainty"],
            fractal_patterns=[
                HarmonicPattern(**pattern) 
                for pattern in analysis_synthesis["fractal_patterns"]
            ],
            temporal_anchor=analysis_synthesis["temporal_anchor"],
            quantum_metadata=analysis_synthesis["quantum_metadata"],
        )
        
        return revelation
        
    except Exception as nexus_anomaly:
        await vault_session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Wavelength synthesis failed: {str(nexus_anomaly)}"
        )


@vitality_portal.get("/health", response_model=VitalityProbe)
async def probe_nexus_vitality(vault_session: AsyncSession = Depends(conjure_vault_session)):
    try:
        await vault_session.execute(text("SELECT 1"))
        vault_heartbeat = True
    except Exception:
        vault_heartbeat = False
    
    return VitalityProbe(
        nexus_status="operational" if vault_heartbeat else "degraded",
        vault_heartbeat=vault_heartbeat,
        temporal_marker=datetime.now(timezone.utc),
    )
