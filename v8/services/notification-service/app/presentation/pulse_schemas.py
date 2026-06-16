from pydantic import BaseModel, Field


class EnrollmentRequest(BaseModel):
    """Schema for receptor enrollment requests"""
    
    channel: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Conduit pathway designation"
    )
    topic: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Subject matter for enrollment"
    )


class EnrollmentManifest(BaseModel):
    """Schema for enrollment confirmation manifest"""
    
    enrollment_id: int
    receptor: str
    pathway: str
    subject: str
    enrollment_status: str
    inscribed_at: str


class TowerStatus(BaseModel):
    """Schema for tower operational status"""
    
    tower_designation: str
    is_operational: bool
    status_timestamp: str
    active_conduits: int
