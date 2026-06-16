import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.launchpad import nexus_gateway
from app.persistence.vault import ChronicleFoundation, conjure_vault_session
from app.persistence.chronicle_entities import WaveformChronicle

TEST_QUANTUM_LINK = "sqlite+aiosqlite:///:memory:"

test_quantum_engine = create_async_engine(TEST_QUANTUM_LINK, echo=False)
TestSessionWeaver = async_sessionmaker(
    test_quantum_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


async def override_vault_session():
    async with TestSessionWeaver() as session:
        yield session


nexus_gateway.dependency_overrides[conjure_vault_session] = override_vault_session


@pytest.fixture
async def initialize_test_vault():
    async with test_quantum_engine.begin() as connection:
        await connection.run_sync(ChronicleFoundation.metadata.create_all)
    yield
    async with test_quantum_engine.begin() as connection:
        await connection.run_sync(ChronicleFoundation.metadata.drop_all)


@pytest.fixture
async def nexus_client(initialize_test_vault):
    async with AsyncClient(
        transport=ASGITransport(app=nexus_gateway),
        base_url="http://test"
    ) as client:
        yield client


class TestNexusPortals:
    
    async def test_root_endpoint(self, nexus_client):
        response = await nexus_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "nexus" in data
        assert "wavelength_portals" in data
    
    async def test_health_probe(self, nexus_client):
        response = await nexus_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "nexus_status" in data
        assert "vault_heartbeat" in data
        assert data["vault_heartbeat"] is True
    
    async def test_analyze_wavelength_trends_success(self, nexus_client):
        inquiry_payload = {
            "ticker_sigil": "AAPL",
            "temporal_span": "30d"
        }
        
        response = await nexus_client.post("/api/v1/analytics/trends", json=inquiry_payload)
        assert response.status_code == 200
        
        revelation = response.json()
        assert revelation["ticker_sigil"] == "AAPL"
        assert "wavelength_signature" in revelation
        assert "harmonic_certainty" in revelation
        assert "fractal_patterns" in revelation
        assert "quantum_metadata" in revelation
        
        assert 0.0 <= revelation["harmonic_certainty"] <= 1.0
        assert len(revelation["fractal_patterns"]) == 3
        
        for pattern in revelation["fractal_patterns"]:
            assert "pattern_cipher" in pattern
            assert "resonance_intensity" in pattern
            assert 0.0 <= pattern["resonance_intensity"] <= 1.0
    
    async def test_analyze_wavelength_trends_different_spans(self, nexus_client):
        spans = ["7d", "30d", "90d", "365d"]
        
        for span in spans:
            inquiry_payload = {
                "ticker_sigil": "TSLA",
                "temporal_span": span
            }
            response = await nexus_client.post("/api/v1/analytics/trends", json=inquiry_payload)
            assert response.status_code == 200
            revelation = response.json()
            assert revelation["quantum_metadata"]["temporal_span"] == span
    
    async def test_ticker_normalization(self, nexus_client):
        inquiry_payload = {
            "ticker_sigil": "  googl  ",
            "temporal_span": "30d"
        }
        
        response = await nexus_client.post("/api/v1/analytics/trends", json=inquiry_payload)
        assert response.status_code == 200
        revelation = response.json()
        assert revelation["ticker_sigil"] == "GOOGL"
    
    async def test_invalid_temporal_span(self, nexus_client):
        inquiry_payload = {
            "ticker_sigil": "MSFT",
            "temporal_span": "invalid"
        }
        
        response = await nexus_client.post("/api/v1/analytics/trends", json=inquiry_payload)
        assert response.status_code == 422
    
    async def test_empty_ticker_rejection(self, nexus_client):
        inquiry_payload = {
            "ticker_sigil": "",
            "temporal_span": "30d"
        }
        
        response = await nexus_client.post("/api/v1/analytics/trends", json=inquiry_payload)
        assert response.status_code == 422
    
    async def test_multiple_analyses_same_ticker(self, nexus_client):
        inquiry_payload = {
            "ticker_sigil": "NVDA",
            "temporal_span": "90d"
        }
        
        response1 = await nexus_client.post("/api/v1/analytics/trends", json=inquiry_payload)
        response2 = await nexus_client.post("/api/v1/analytics/trends", json=inquiry_payload)
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        revelation1 = response1.json()
        revelation2 = response2.json()
        
        assert revelation1["wavelength_signature"] == revelation2["wavelength_signature"]
