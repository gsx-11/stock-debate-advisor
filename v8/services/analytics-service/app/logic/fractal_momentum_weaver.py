import math
from typing import List, Tuple
from datetime import datetime, timezone
from app.presentation.wavelength_schemas import HarmonicPattern


class FractalMomentumWeaver:
    
    WAVELENGTH_CIPHERS = {
        "ascending_helix": ["climbing", "surging", "elevating"],
        "descending_vortex": ["declining", "sliding", "retreating"],
        "oscillating_nexus": ["sideways", "ranging", "fluctuating"],
        "volatile_chaos": ["erratic", "unstable", "turbulent"],
    }
    
    def __init__(self, ticker_sigil: str, temporal_span: str):
        self.ticker_sigil = ticker_sigil
        self.temporal_span = temporal_span
        self.phase_multiplier = self._calculate_phase_multiplier()
        
    def _calculate_phase_multiplier(self) -> float:
        span_weights = {"7d": 2.3, "30d": 1.7, "90d": 1.2, "365d": 0.8}
        return span_weights.get(self.temporal_span, 1.0)
    
    def _generate_quantum_seed(self) -> int:
        sigil_hash = sum(ord(char) * (idx + 1) for idx, char in enumerate(self.ticker_sigil))
        temporal_factor = hash(self.temporal_span) % 997
        return (sigil_hash * temporal_factor) % 10000
    
    def _compute_harmonic_oscillations(self) -> List[float]:
        quantum_seed = self._generate_quantum_seed()
        oscillations = []
        
        for wave_index in range(13):
            frequency = (quantum_seed + wave_index * 73) / 10000.0
            amplitude = math.sin(frequency * math.pi * 2) * self.phase_multiplier
            phase_shift = math.cos(wave_index * 0.618) * 0.5
            oscillations.append(amplitude + phase_shift)
        
        return oscillations
    
    def _derive_wavelength_signature(self, oscillations: List[float]) -> Tuple[str, str]:
        momentum_vector = sum(oscillations) / len(oscillations)
        volatility_metric = sum(abs(o - momentum_vector) for o in oscillations) / len(oscillations)
        
        if volatility_metric > 1.2:
            primary_wavelength = "volatile_chaos"
            phase_descriptor = "turbulent"
        elif momentum_vector > 0.4:
            primary_wavelength = "ascending_helix"
            phase_descriptor = "surging" if momentum_vector > 0.7 else "climbing"
        elif momentum_vector < -0.4:
            primary_wavelength = "descending_vortex"
            phase_descriptor = "sliding" if momentum_vector < -0.7 else "declining"
        else:
            primary_wavelength = "oscillating_nexus"
            phase_descriptor = "ranging"
        
        return primary_wavelength, phase_descriptor
    
    def _calculate_harmonic_certainty(self, oscillations: List[float], wavelength: str) -> float:
        consistency_factor = 1.0 - (max(oscillations) - min(oscillations)) / 4.0
        consistency_factor = max(0.1, min(consistency_factor, 1.0))
        
        wavelength_boost = {
            "ascending_helix": 0.15,
            "descending_vortex": 0.12,
            "oscillating_nexus": 0.08,
            "volatile_chaos": -0.1,
        }
        
        base_certainty = consistency_factor + wavelength_boost.get(wavelength, 0.0)
        
        temporal_adjustment = {"7d": 0.05, "30d": 0.1, "90d": 0.15, "365d": 0.2}
        adjusted_certainty = base_certainty + temporal_adjustment.get(self.temporal_span, 0.0)
        
        return max(0.0, min(adjusted_certainty, 1.0))
    
    def _weave_fractal_patterns(
        self, oscillations: List[float], primary_wavelength: str, phase: str
    ) -> List[HarmonicPattern]:
        patterns = []
        
        pattern_definitions = [
            ("fibonacci_spiral", oscillations[0] * oscillations[8]),
            ("golden_resonance", oscillations[3] * oscillations[10]),
            ("silver_harmonic", oscillations[5] * oscillations[12]),
        ]
        
        for pattern_name, intensity_raw in pattern_definitions:
            normalized_intensity = (intensity_raw + 2.0) / 4.0
            normalized_intensity = max(0.0, min(normalized_intensity, 1.0))
            
            patterns.append(HarmonicPattern(
                pattern_cipher=f"{pattern_name}_{self.ticker_sigil.lower()}",
                resonance_intensity=round(normalized_intensity, 4),
                oscillation_phase=phase
            ))
        
        return patterns
    
    def synthesize_wavelength_analysis(self) -> dict:
        oscillations = self._compute_harmonic_oscillations()
        wavelength_sig, phase_desc = self._derive_wavelength_signature(oscillations)
        certainty = self._calculate_harmonic_certainty(oscillations, wavelength_sig)
        patterns = self._weave_fractal_patterns(oscillations, wavelength_sig, phase_desc)
        
        quantum_metadata = {
            "oscillation_count": len(oscillations),
            "momentum_vector": round(sum(oscillations) / len(oscillations), 4),
            "volatility_index": round(
                sum(abs(o - sum(oscillations) / len(oscillations)) for o in oscillations) / len(oscillations), 4
            ),
            "phase_multiplier": self.phase_multiplier,
            "temporal_span": self.temporal_span,
        }
        
        return {
            "wavelength_signature": wavelength_sig,
            "harmonic_certainty": round(certainty, 4),
            "fractal_patterns": [p.model_dump() for p in patterns],
            "temporal_anchor": datetime.now(timezone.utc),
            "quantum_metadata": quantum_metadata,
        }
