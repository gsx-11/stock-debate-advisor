from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class NexusQuantumParams(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
    
    quantum_link: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/analytics_quantum"
    nexus_port: int = 8005
    cipher_phrase: str = "ultra-secret-nexus-cipher-key-for-analytics-wavefront"
    reality_layer: str = "development"


@lru_cache
def fetch_quantum_params() -> NexusQuantumParams:
    return NexusQuantumParams()
