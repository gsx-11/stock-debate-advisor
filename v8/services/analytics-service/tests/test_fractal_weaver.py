import pytest
from app.logic.fractal_momentum_weaver import FractalMomentumWeaver


class TestFractalMomentumWeaver:
    
    def test_weaver_initialization(self):
        weaver = FractalMomentumWeaver("AAPL", "30d")
        assert weaver.ticker_sigil == "AAPL"
        assert weaver.temporal_span == "30d"
        assert weaver.phase_multiplier == 1.7
    
    def test_phase_multiplier_calculation(self):
        weaver_7d = FractalMomentumWeaver("TSLA", "7d")
        weaver_365d = FractalMomentumWeaver("TSLA", "365d")
        assert weaver_7d.phase_multiplier == 2.3
        assert weaver_365d.phase_multiplier == 0.8
    
    def test_quantum_seed_generation(self):
        weaver1 = FractalMomentumWeaver("AAPL", "30d")
        weaver2 = FractalMomentumWeaver("GOOGL", "30d")
        seed1 = weaver1._generate_quantum_seed()
        seed2 = weaver2._generate_quantum_seed()
        assert seed1 != seed2
        assert 0 <= seed1 < 10000
        assert 0 <= seed2 < 10000
    
    def test_harmonic_oscillations_count(self):
        weaver = FractalMomentumWeaver("MSFT", "90d")
        oscillations = weaver._compute_harmonic_oscillations()
        assert len(oscillations) == 13
        assert all(isinstance(o, float) for o in oscillations)
    
    def test_wavelength_signature_derivation(self):
        weaver = FractalMomentumWeaver("NVDA", "30d")
        oscillations = weaver._compute_harmonic_oscillations()
        wavelength, phase = weaver._derive_wavelength_signature(oscillations)
        assert wavelength in ["ascending_helix", "descending_vortex", "oscillating_nexus", "volatile_chaos"]
        assert isinstance(phase, str)
        assert len(phase) > 0
    
    def test_harmonic_certainty_range(self):
        weaver = FractalMomentumWeaver("META", "90d")
        oscillations = weaver._compute_harmonic_oscillations()
        wavelength, _ = weaver._derive_wavelength_signature(oscillations)
        certainty = weaver._calculate_harmonic_certainty(oscillations, wavelength)
        assert 0.0 <= certainty <= 1.0
    
    def test_fractal_patterns_generation(self):
        weaver = FractalMomentumWeaver("AMZN", "30d")
        oscillations = weaver._compute_harmonic_oscillations()
        wavelength, phase = weaver._derive_wavelength_signature(oscillations)
        patterns = weaver._weave_fractal_patterns(oscillations, wavelength, phase)
        assert len(patterns) == 3
        assert all(0.0 <= p.resonance_intensity <= 1.0 for p in patterns)
        assert all("amzn" in p.pattern_cipher for p in patterns)
    
    def test_complete_wavelength_synthesis(self):
        weaver = FractalMomentumWeaver("SPY", "7d")
        analysis = weaver.synthesize_wavelength_analysis()
        
        assert "wavelength_signature" in analysis
        assert "harmonic_certainty" in analysis
        assert "fractal_patterns" in analysis
        assert "temporal_anchor" in analysis
        assert "quantum_metadata" in analysis
        
        assert 0.0 <= analysis["harmonic_certainty"] <= 1.0
        assert len(analysis["fractal_patterns"]) == 3
        assert analysis["quantum_metadata"]["oscillation_count"] == 13
        assert analysis["quantum_metadata"]["temporal_span"] == "7d"
    
    def test_consistent_results_for_same_input(self):
        weaver1 = FractalMomentumWeaver("COIN", "30d")
        weaver2 = FractalMomentumWeaver("COIN", "30d")
        
        analysis1 = weaver1.synthesize_wavelength_analysis()
        analysis2 = weaver2.synthesize_wavelength_analysis()
        
        assert analysis1["wavelength_signature"] == analysis2["wavelength_signature"]
        assert analysis1["harmonic_certainty"] == analysis2["harmonic_certainty"]
