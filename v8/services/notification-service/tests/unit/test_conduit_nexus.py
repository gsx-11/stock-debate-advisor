import pytest
from unittest.mock import AsyncMock, MagicMock
from app.logic.conduit_nexus import ConduitNexus


@pytest.fixture
def nexus_fixture():
    """Create conduit nexus instance"""
    return ConduitNexus()


@pytest.fixture
def mock_conduit_wire():
    """Create mock WebSocket conduit"""
    wire_mock = MagicMock()
    wire_mock.accept = AsyncMock()
    wire_mock.send_text = AsyncMock()
    wire_mock.send_json = AsyncMock()
    return wire_mock


class TestConduitNexus:
    """Test suite for conduit nexus operations"""
    
    async def test_establish_conduit_creates_connection(
        self,
        nexus_fixture,
        mock_conduit_wire
    ):
        """Verify conduit establishment"""
        receptor_id = "receptor_alpha_001"
        
        await nexus_fixture.establish_conduit(
            receptor_id=receptor_id,
            conduit_wire=mock_conduit_wire
        )
        
        mock_conduit_wire.accept.assert_called_once()
        assert receptor_id in nexus_fixture.active_conduits
        assert mock_conduit_wire in nexus_fixture.active_conduits[receptor_id]
        assert mock_conduit_wire in nexus_fixture.conduit_chronicles
    
    async def test_sever_conduit_removes_connection(
        self,
        nexus_fixture,
        mock_conduit_wire
    ):
        """Verify conduit severance"""
        receptor_id = "receptor_beta_002"
        
        await nexus_fixture.establish_conduit(
            receptor_id=receptor_id,
            conduit_wire=mock_conduit_wire
        )
        
        nexus_fixture.sever_conduit(
            receptor_id=receptor_id,
            conduit_wire=mock_conduit_wire
        )
        
        assert receptor_id not in nexus_fixture.active_conduits
        assert mock_conduit_wire not in nexus_fixture.conduit_chronicles
    
    async def test_transmit_pulse_delivers_cargo(
        self,
        nexus_fixture,
        mock_conduit_wire
    ):
        """Verify pulse transmission"""
        receptor_id = "receptor_gamma_003"
        pulse_cargo = {"beacon_type": "alert", "payload": "test_data"}
        
        await nexus_fixture.establish_conduit(
            receptor_id=receptor_id,
            conduit_wire=mock_conduit_wire
        )
        
        await nexus_fixture.transmit_pulse_to_receptor(
            receptor_id=receptor_id,
            pulse_cargo=pulse_cargo
        )
        
        mock_conduit_wire.send_text.assert_called_once()
        assert nexus_fixture.conduit_chronicles[mock_conduit_wire]["pulse_tally"] == 1
    
    async def test_compile_nexus_metrics_accurate(
        self,
        nexus_fixture,
        mock_conduit_wire
    ):
        """Verify metrics compilation"""
        receptor_id = "receptor_delta_004"
        
        await nexus_fixture.establish_conduit(
            receptor_id=receptor_id,
            conduit_wire=mock_conduit_wire
        )
        
        metrics = nexus_fixture.compile_nexus_metrics()
        
        assert metrics["receptor_count"] == 1
        assert metrics["conduit_count"] == 1
        assert receptor_id in metrics["receptor_roster"]
