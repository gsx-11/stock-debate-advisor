from pydantic_settings import BaseSettings, SettingsConfigDict


class TowerBlueprint(BaseSettings):
    """Blueprint for beacon tower configuration"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    beacon_tower_port: int = 8006
    beacon_tower_bind: str = "0.0.0.0"
    
    persistence_vault_uri: str = "postgresql+asyncpg://notifuser:notifpass@localhost:5432/notifdb"
    
    conduit_heartbeat_cycle: int = 30
    conduit_response_wait: int = 10
    
    verbosity_tier: str = "INFO"


tower_blueprint = TowerBlueprint()
