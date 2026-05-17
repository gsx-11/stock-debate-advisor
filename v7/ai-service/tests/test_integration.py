"""
Integration tests for Stock Debate Advisor v3.0.

Tests cover:
1. Engine internals (data loading, analysis, price conditions)
2. Auto vs Human-in-loop mode
3. LangGraph orchestrator (classifier routing, all workflows)
4. FastAPI endpoints (debate, continue, LangGraph query)
5. Risk manager agent
"""
import sys
import os
import json
import pytest

# Ensure imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from src.core.engine import (
    DebateEngine,
    DataLoader,
    _fundamental_analysis,
    _technical_analysis,
    _sentiment_analysis,
    _risk_manager_analysis,
    _judge_analysis,
    _compute_sma,
    _compute_rsi,
    _compute_macd,
    _fmt,
)
from src.core.constants import (
    AGENT_PROMPTS,
    DEBATE_MODE_AUTO,
    DEBATE_MODE_HUMAN,
    AUTO_MODE_AGENTS,
    QUERY_CATEGORIES,
)
from src.core.langgraph_orchestrator import (
    classify_query,
    run_graph,
    build_debate_graph,
    DebateState,
)
from src.utils.models import (
    DebateRequest,
    DebateContinueRequest,
    DebateResponse,
    RoundResponse,
    HealthResponse,
)


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def data_loader():
    return DataLoader()


@pytest.fixture
def engine():
    return DebateEngine()


@pytest.fixture
def sample_stock_data(data_loader):
    """Load MBB data (known to exist from crawl)."""
    return data_loader.load_stock_data("MBB")


# ── Unit Tests: Technical Helpers ─────────────────────────────

class TestTechnicalHelpers:
    def test_compute_sma(self):
        closes = [10.0, 11.0, 12.0, 13.0, 14.0]
        assert _compute_sma(closes, 3) == pytest.approx(13.0)
        assert _compute_sma(closes, 5) == pytest.approx(12.0)
        assert _compute_sma(closes, 10) is None

    def test_compute_rsi(self):
        # Generate uptrending prices
        closes = [100 + i * 0.5 for i in range(20)]
        rsi = _compute_rsi(closes)
        assert rsi is not None
        assert 50 <= rsi <= 100  # Uptrend => RSI > 50

    def test_compute_macd(self):
        closes = [100 + i * 0.3 for i in range(30)]
        macd = _compute_macd(closes)
        assert macd["macd"] is not None
        assert macd["signal"] is not None
        assert macd["histogram"] is not None

    def test_fmt_large_numbers(self):
        assert _fmt(1_500_000_000) == "1.50B"
        assert _fmt(2_500_000) == "2.50M"
        assert _fmt(1_500) == "1.50K"
        assert _fmt(42.5) == "42.50"

    def test_fmt_none(self):
        assert _fmt(None) == "N/A"

    def test_fmt_nan(self):
        assert _fmt(float("nan")) == "N/A"


# ── Unit Tests: Data Loader ──────────────────────────────────

class TestDataLoader:
    def test_load_existing_stock(self, data_loader):
        data = data_loader.load_stock_data("MBB")
        assert "error" not in data
        assert "company_info" in data
        assert "financial_reports" in data
        assert "ohlc_prices" in data

    def test_load_nonexistent_stock(self, data_loader):
        data = data_loader.load_stock_data("INVALID_TICKER_XYZ")
        assert "error" in data


# ── Integration Tests: Analysis Functions with Price Conditions ─

class TestAnalysisPriceConditions:
    """Every analysis output must include price conditions."""

    def test_fundamental_has_price_condition(self, sample_stock_data):
        result = _fundamental_analysis("MBB", "3 months", sample_stock_data, 1)
        assert any(kw in result for kw in ["BUY below", "SELL above", "HOLD at"])

    def test_technical_has_price_condition(self, sample_stock_data):
        result = _technical_analysis("MBB", "3 months", sample_stock_data, 1)
        assert any(kw in result for kw in ["BUY below", "SELL above", "HOLD at"])

    def test_sentiment_has_price_condition(self, sample_stock_data):
        result = _sentiment_analysis("MBB", "3 months", sample_stock_data, 1)
        assert any(kw in result for kw in ["BUY below", "SELL above", "HOLD at"])

    def test_risk_manager_has_stop_loss(self, sample_stock_data):
        result = _risk_manager_analysis("MBB", "3 months", sample_stock_data, 1)
        assert "stop-loss" in result.lower() or "Stop-loss" in result

    def test_risk_manager_has_take_profit(self, sample_stock_data):
        result = _risk_manager_analysis("MBB", "3 months", sample_stock_data, 1)
        assert "take-profit" in result.lower() or "take_profit" in result.lower()

    def test_judge_has_price_condition(self, sample_stock_data):
        responses = {
            "fundamental": "BUY below 25,000 VND for 3 months because strong growth.",
            "technical": "BUY below 26,000 VND for 3 months because SMA support.",
            "sentiment": "HOLD at 24,000-27,000 VND for 3 months because mixed sentiment.",
            "risk_manager": "Stop-loss at 22,000 VND, take-profit at 28,000 VND.",
        }
        result = _judge_analysis("MBB", "3 months", 2, 5, responses, sample_stock_data)
        assert "CONCLUDE" in result
        assert any(kw in result for kw in ["BUY below", "SELL above", "HOLD at"])

    def test_round2_fundamental_has_price_condition(self, sample_stock_data):
        result = _fundamental_analysis("MBB", "3 months", sample_stock_data, 2)
        assert any(kw in result for kw in ["BUY below", "SELL above", "HOLD at"])

    def test_round2_technical_has_price_condition(self, sample_stock_data):
        result = _technical_analysis("MBB", "3 months", sample_stock_data, 2)
        assert any(kw in result for kw in ["BUY below", "SELL above", "HOLD at"])


# ── Integration Tests: Debate Engine ─────────────────────────

class TestDebateEngine:
    def test_auto_mode_debate(self, engine):
        result = engine.debate("MBB", "3 months", 1, 3, mode=DEBATE_MODE_AUTO)
        assert result["status"] == "completed"
        assert result["mode"] == "auto"
        assert result["actual_rounds"] >= 1
        assert result["final_recommendation"] in ("BUY", "HOLD", "SELL")
        assert result["confidence"] in ("Low", "Medium", "High")
        assert len(result["rounds"]) >= 1

    def test_human_mode_pauses(self, engine):
        result = engine.debate("MBB", "3 months", 2, 5, mode=DEBATE_MODE_HUMAN)
        # Human mode should pause after round 1 if debate should continue
        assert result["status"] in ("awaiting_human_input", "completed")
        if result["status"] == "awaiting_human_input":
            assert result["actual_rounds"] == 1

    def test_debate_has_risk_manager(self, engine):
        result = engine.debate("MBB", "3 months", 1, 2, mode=DEBATE_MODE_AUTO)
        for round_data in result["rounds"]:
            assert "risk_manager" in round_data
            assert round_data["risk_manager"]  # Not empty

    def test_debate_with_human_input(self, engine):
        result = engine.debate(
            "FPT", "6 months", 1, 3,
            mode=DEBATE_MODE_AUTO,
            human_input="I am concerned about tech sector headwinds",
        )
        assert result["status"] == "completed"

    def test_debate_multiple_tickers(self, engine):
        for ticker in ["MBB", "FPT", "HPG"]:
            result = engine.debate(ticker, "3 months", 1, 2, mode=DEBATE_MODE_AUTO)
            assert result["status"] == "completed"
            assert result["ticker"] == ticker

    def test_debate_invalid_ticker(self, engine):
        with pytest.raises(ValueError, match="No data found"):
            engine.debate("INVALID_XYZ", "3 months", 1, 2)


# ── Integration Tests: Agent Prompts ─────────────────────────

class TestAgentPrompts:
    def test_all_prompts_have_price_conditions_section(self):
        for agent, prompt in AGENT_PROMPTS.items():
            assert "PRICE CONDITIONS ARE MANDATORY" in prompt, f"{agent} prompt missing price conditions section"

    def test_prompt_agents_defined(self):
        assert "fundamental" in AGENT_PROMPTS
        assert "technical" in AGENT_PROMPTS
        assert "sentiment" in AGENT_PROMPTS
        assert "judge" in AGENT_PROMPTS
        assert "risk_manager" in AGENT_PROMPTS

    def test_auto_mode_agents_list(self):
        assert "fundamental" in AUTO_MODE_AGENTS
        assert "technical" in AUTO_MODE_AGENTS
        assert "sentiment" in AUTO_MODE_AGENTS
        assert "risk_manager" in AUTO_MODE_AGENTS


# ── Integration Tests: LangGraph Orchestrator ─────────────────

class TestLangGraphClassifier:
    def test_classify_stock_analysis(self):
        state: DebateState = {"query": "analyze MBB for 3 months", "ticker": "MBB"}
        result = classify_query(state)
        assert result["category"] == "stock_analysis"

    def test_classify_price_check(self):
        state: DebateState = {"query": "what is the current price of FPT", "ticker": "FPT"}
        result = classify_query(state)
        assert result["category"] == "price_check"

    def test_classify_comparison(self):
        state: DebateState = {"query": "compare MBB vs FPT", "ticker": "MBB,FPT"}
        result = classify_query(state)
        assert result["category"] == "comparison"

    def test_classify_risk(self):
        state: DebateState = {"query": "risk assessment for HPG position", "ticker": "HPG"}
        result = classify_query(state)
        assert result["category"] == "risk_assessment"

    def test_classify_market_overview(self):
        state: DebateState = {"query": "VN30 market overview today", "ticker": ""}
        result = classify_query(state)
        assert result["category"] == "market_overview"


class TestLangGraphWorkflows:
    def test_stock_analysis_workflow(self):
        result = run_graph(ticker="MBB", query="should I buy MBB stock", timeframe="3 months")
        assert result.get("status") == "completed" or "final_recommendation" in result

    def test_price_check_workflow(self):
        result = run_graph(ticker="MBB", query="what is the current price of MBB")
        assert result.get("category") == "price_check" or result.get("status") == "completed"
        assert "price" in result or "ticker" in result

    def test_risk_assessment_workflow(self):
        result = run_graph(ticker="MBB", query="risk assessment for my MBB position")
        assert result.get("status") == "completed"
        assert result.get("category") == "risk_assessment"

    def test_comparison_workflow(self):
        result = run_graph(ticker="MBB,FPT", query="compare MBB vs FPT")
        assert result.get("status") == "completed"
        assert result.get("category") == "comparison"

    def test_market_overview_workflow(self):
        result = run_graph(ticker="", query="VN30 market overview")
        assert result.get("status") == "completed"
        assert result.get("category") == "market_overview"

    def test_graph_compiles(self):
        graph = build_debate_graph()
        assert graph is not None


# ── Integration Tests: Pydantic Models ────────────────────────

class TestModels:
    def test_debate_request_defaults(self):
        req = DebateRequest(ticker="MBB")
        assert req.mode == "auto"
        assert req.timeframe == "3 months"
        assert req.min_rounds == 1
        assert req.max_rounds == 5

    def test_debate_request_human_mode(self):
        req = DebateRequest(ticker="MBB", mode="human")
        assert req.mode == "human"

    def test_debate_continue_request(self):
        req = DebateContinueRequest(session_id="test_session", ticker="MBB", human_input="Focus on risk factors")
        assert req.human_input == "Focus on risk factors"
        assert req.session_id == "test_session"

    def test_round_response_with_risk_manager(self):
        rr = RoundResponse(
            round_num=1,
            fundamental="test",
            technical="test",
            sentiment="test",
            risk_manager="test risk",
            judge_decision="CONTINUE",
        )
        assert rr.risk_manager == "test risk"

    def test_debate_response_new_fields(self):
        dr = DebateResponse(
            ticker="MBB",
            timeframe="3 months",
            actual_rounds=2,
            rounds=[],
            mode="auto",
            status="completed",
            final_recommendation="BUY",
            confidence="High",
            rationale="test",
            risks="test",
            monitor="test",
            price_target="25,000 VND",
        )
        assert dr.mode == "auto"
        assert dr.status == "completed"
        assert dr.price_target == "25,000 VND"

    def test_health_version(self):
        h = HealthResponse()
        assert h.version == "3.0"


# ── Integration Tests: FastAPI App ────────────────────────────

class TestFastAPIEndpoints:
    """Test FastAPI endpoints using TestClient."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from fastapi.testclient import TestClient
        from src.handlers import main as main_module
        from src.handlers.main import app

        # Initialize engine that lifespan would normally create
        main_module.engine = DebateEngine()
        self.client = TestClient(app)
        yield
        main_module.engine = None

    def test_health(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "3.0"

    def test_debate_auto(self):
        resp = self.client.post("/api/v1/debate/start", json={
            "ticker": "MBB",
            "timeframe": "3 months",
            "min_rounds": 1,
            "max_rounds": 2,
            "mode": "auto",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "auto"
        assert data["status"] == "completed"
        assert data["final_recommendation"] in ("BUY", "HOLD", "SELL")

    def test_debate_human_mode(self):
        resp = self.client.post("/api/v1/debate/start", json={
            "ticker": "MBB",
            "timeframe": "3 months",
            "min_rounds": 2,
            "max_rounds": 5,
            "mode": "human",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("awaiting_human_input", "completed")

    def test_debate_continue(self):
        # First, start a human-mode debate to get a session_id
        start_resp = self.client.post("/api/v1/debate/start", json={
            "ticker": "MBB",
            "timeframe": "3 months",
            "mode": "human",
            "min_rounds": 1,
            "max_rounds": 3,
        })
        assert start_resp.status_code == 200
        session_id = start_resp.json()["session_id"]
        
        # Now continue the debate with human feedback
        resp = self.client.post("/api/v1/debate/continue", json={
            "session_id": session_id,
            "ticker": "MBB",
            "timeframe": "3 months",
            "human_input": "Focus more on credit risk for banking sector",
            "min_rounds": 1,
            "max_rounds": 3,
        })
        assert resp.status_code == 200

    def test_legacy_debate_endpoint(self):
        resp = self.client.post("/debate", json={
            "ticker": "FPT",
            "timeframe": "6 months",
            "min_rounds": 1,
            "max_rounds": 2,
        })
        assert resp.status_code == 200

    def test_langgraph_query_stock_analysis(self):
        resp = self.client.post("/api/v2/query", json={
            "query": "should I buy MBB stock for 3 months",
            "ticker": "MBB",
            "timeframe": "3 months",
        })
        assert resp.status_code == 200

    def test_langgraph_query_price_check(self):
        resp = self.client.post("/api/v2/query", json={
            "query": "what is the current price of MBB",
            "ticker": "MBB",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "price" in data or "ticker" in data

    def test_langgraph_query_comparison(self):
        resp = self.client.post("/api/v2/query", json={
            "query": "compare MBB vs FPT performance",
            "ticker": "MBB,FPT",
        })
        assert resp.status_code == 200

    def test_langgraph_query_risk(self):
        resp = self.client.post("/api/v2/query", json={
            "query": "risk assessment and stop-loss for HPG",
            "ticker": "HPG",
        })
        assert resp.status_code == 200

    def test_langgraph_query_market_overview(self):
        resp = self.client.post("/api/v2/query", json={
            "query": "VN30 market overview",
            "ticker": "",
        })
        assert resp.status_code == 200

    def test_debate_rounds_have_risk_manager(self):
        resp = self.client.post("/api/v1/debate/start", json={
            "ticker": "MBB",
            "min_rounds": 1,
            "max_rounds": 2,
            "mode": "auto",
        })
        assert resp.status_code == 200
        data = resp.json()
        for rnd in data["rounds"]:
            assert "risk_manager" in rnd
