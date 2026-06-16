import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.presentation.beacon_tower import tower_instance


@pytest.fixture
def tower_client():
    """Create tower test client"""
    return TestClient(tower_instance)


class TestBeaconTowerEndpoints:
    """Test suite for beacon tower endpoints"""
    
    def test_tower_status_endpoint_operational(self, tower_client):
        """Verify tower status reporting"""
        response = tower_client.get("/health")
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["tower_designation"] == "beacon-transmission-tower"
        assert response_data["is_operational"] is True
        assert "status_timestamp" in response_data
        assert "active_conduits" in response_data
    
    @patch("app.presentation.beacon_tower.PulseConductor")
    def test_enrollment_endpoint_orchestrates_registration(
        self,
        mock_conductor_class,
        tower_client
    ):
        """Verify receptor enrollment orchestration"""
        mock_conductor = mock_conductor_class.return_value
        mock_conductor.orchestrate_receptor_enrollment = AsyncMock(
            return_value={
                "enrollment_id": 1,
                "receptor": "system_user",
                "pathway": "email_conduit",
                "subject": "stock_alerts",
                "enrollment_status": "operational",
                "inscribed_at": "2024-01-01T00:00:00Z"
            }
        )
        
        enrollment_payload = {
            "channel": "email_conduit",
            "topic": "stock_alerts"
        }
        
        response = tower_client.post(
            "/api/v1/notifications/subscribe",
            json=enrollment_payload
        )
        
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["pathway"] == "email_conduit"
        assert response_data["subject"] == "stock_alerts"
        assert response_data["enrollment_status"] == "operational"
