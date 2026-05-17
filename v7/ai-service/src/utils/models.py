from typing import Dict, Any, Literal
from pydantic import BaseModel, Field

class DebateRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    timeframe: str = Field(default="3 months", description="Investment timeframe (1 month, 3 months, 6 months, 1 year)")
    min_rounds: int = Field(default=1, ge=1, le=5)
    max_rounds: int = Field(default=5, ge=1, le=10)
    mode: Literal["auto", "human"] = Field(default="auto", description="Auto: 5 agents debate automatically. Human: pause for human input between rounds")

class DebateContinueRequest(BaseModel):
    session_id: str = Field(..., description="Session ID from the paused debate")
    ticker: str = Field(..., description="Stock ticker symbol")
    timeframe: str = Field(default="3 months")
    human_input: str = Field(..., description="Human feedback/direction for the next debate round")
    min_rounds: int = Field(default=1, ge=1, le=5)
    max_rounds: int = Field(default=5, ge=1, le=10)

class RoundResponse(BaseModel):
    round_num: int
    fundamental: str
    technical: str
    sentiment: str
    risk_manager: str = ""
    judge_decision: str
    human_input: str | None = None

class DebateResponse(BaseModel):
    session_id: str = ""
    ticker: str
    timeframe: str
    actual_rounds: int
    rounds: list[RoundResponse]
    mode: str = "auto"
    status: str = "completed"
    final_recommendation: str
    confidence: str
    confidence_percent: float = 0.0
    decision_qualified: bool = False
    rationale: str
    risks: str
    monitor: str
    price_target: str = ""

class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "3.0"
