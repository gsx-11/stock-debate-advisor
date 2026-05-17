"""
Database models for Stock Debate Advisor
Handles DynamoDB table definitions and access patterns
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import json


class DebateStatus(str, Enum):
    """Debate status enum"""
    INITIATED = "INITIATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class Recommendation(str, Enum):
    """Investment recommendation"""
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


class ConfidenceLevel(str, Enum):
    """Confidence level"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class VerdictItem:
    """Final verdict from debate"""
    recommendation: Recommendation
    confidence: ConfidenceLevel
    rationale: str
    score: float


@dataclass
class DebateRecord:
    """Debate session record"""
    debate_id: str
    symbol: str
    status: DebateStatus
    rounds: int
    created_at: str
    mode: str = "auto"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    verdict: Optional[Dict[str, Any]] = None
    debate_summary: Optional[str] = None
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
    price_target: Optional[str] = None
    risk_assessment: Optional[str] = None

    def to_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format"""
        item = asdict(self)
        # Convert verdict to JSON string for DynamoDB
        if self.verdict:
            item['verdict'] = json.dumps(self.verdict)
        return item

    @classmethod
    def from_item(cls, item: Dict[str, Any]) -> 'DebateRecord':
        """Create from DynamoDB item"""
        if 'verdict' in item and item['verdict']:
            item['verdict'] = json.loads(item['verdict']) if isinstance(item['verdict'], str) else item['verdict']
        return cls(**item)


@dataclass
class CompanyRecord:
    """Company/stock record"""
    symbol: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    last_updated: Optional[str] = None

    def to_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format"""
        return asdict(self)

    @classmethod
    def from_item(cls, item: Dict[str, Any]) -> 'CompanyRecord':
        """Create from DynamoDB item"""
        return cls(**item)


@dataclass
class FinancialReportRecord:
    """Financial report/metrics record"""
    symbol: str
    report_date: str
    report_type: str  # BALANCE_SHEET, INCOME_STATEMENT, CASH_FLOW, etc.
    metrics: Dict[str, Any]
    fetched_at: str

    def to_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format"""
        item = asdict(self)
        item['metrics'] = json.dumps(self.metrics)
        return item

    @classmethod
    def from_item(cls, item: Dict[str, Any]) -> 'FinancialReportRecord':
        """Create from DynamoDB item"""
        if 'metrics' in item and isinstance(item['metrics'], str):
            item['metrics'] = json.loads(item['metrics'])
        return cls(**item)


@dataclass
class OhlcPriceRecord:
    """OHLC price data"""
    symbol: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int

    def to_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format"""
        return asdict(self)

    @classmethod
    def from_item(cls, item: Dict[str, Any]) -> 'OhlcPriceRecord':
        """Create from DynamoDB item"""
        return cls(**item)
