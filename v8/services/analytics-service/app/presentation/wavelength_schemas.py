from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import List


class WavelengthInquiry(BaseModel):
    ticker_sigil: str = Field(..., min_length=1, max_length=12, description="Stock ticker symbol")
    temporal_span: str = Field(..., pattern="^(7d|30d|90d|365d)$", description="Analysis period")
    
    @field_validator("ticker_sigil")
    @classmethod
    def normalize_ticker_sigil(cls, sigil_value: str) -> str:
        return sigil_value.upper().strip()


class HarmonicPattern(BaseModel):
    pattern_cipher: str
    resonance_intensity: float = Field(..., ge=0.0, le=1.0)
    oscillation_phase: str


class WavelengthRevelation(BaseModel):
    ticker_sigil: str
    wavelength_signature: str
    harmonic_certainty: float = Field(..., ge=0.0, le=1.0)
    fractal_patterns: List[HarmonicPattern]
    temporal_anchor: datetime
    quantum_metadata: dict


class VitalityProbe(BaseModel):
    nexus_status: str
    vault_heartbeat: bool
    temporal_marker: datetime
