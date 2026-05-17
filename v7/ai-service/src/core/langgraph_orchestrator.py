"""
LangGraph-based orchestrator for Stock Debate Advisor.

Implements a StateGraph with:
1. Classifier node — routes user queries to the appropriate workflow
2. Stock analysis workflow — full multi-agent debate with price conditions
3. Price check workflow — quick lookup without debate
4. Risk assessment workflow — focused risk analysis
5. Comparison workflow — side-by-side stock comparison

Best practices applied:
- Typed state with TypedDict
- Conditional routing via classifier
- Structured tool calling pattern
- Checkpoint-ready design for human-in-loop
"""
from typing import Any, Literal
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END

from src.core.constants import (
    DEBATE_MODE_AUTO,
    DEBATE_MODE_HUMAN,
    QUERY_CATEGORIES,
)
from src.core.engine import DebateEngine, DataLoader, _fmt


# ── State definitions ────────────────────────────────────────

class DebateState(TypedDict, total=False):
    """Shared state flowing through the LangGraph."""
    # Input
    query: str
    ticker: str
    timeframe: str
    min_rounds: int
    max_rounds: int
    mode: str  # "auto" or "human"
    human_input: str | None

    # Classifier output
    category: str  # key from QUERY_CATEGORIES

    # Debate state
    rounds: list[dict[str, Any]]
    current_round: int
    should_continue: bool

    # Output
    status: str  # "completed", "awaiting_human_input", "error"
    result: dict[str, Any]
    error: str


# ── Node functions ────────────────────────────────────────────

def classify_query(state: DebateState) -> DebateState:
    """Classifier node: route user query to the appropriate workflow.
    
    Uses keyword matching for the local engine. In production with Bedrock,
    this would be an LLM call to classify the intent.
    """
    import re
    
    query_original = state.get("query") or ""
    query_lower = query_original.lower()
    ticker = state.get("ticker", "")
    
    # Extract ticker from query if not provided
    # VN30 stocks: ACB, BCM, BID, BVH, CTG, FPT, GAS, GVR, HDB, HPG, KDH, MBB, MSN, MWG, 
    # NVL, PNJ, PLX, POW, PVD, PVT, REE, SAB, SBT, TCB, TPB, VCB, VHM, VIB, VJC, VNM
    if not ticker:
        ticker_match = re.search(r'\b([A-Z]{1,4})(?:\.VN)?\b', query_original)
        if ticker_match:
            extracted = ticker_match.group(1)
            # Only accept valid VN30 tickers
            valid_tickers = {'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 
                           'KDH', 'MBB', 'MSN', 'MWG', 'NVL', 'PNJ', 'PLX', 'POW', 'PVD', 'PVT', 
                           'REE', 'SAB', 'SBT', 'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VJC', 'VNM'}
            if extracted in valid_tickers:
                ticker = extracted

    # Rule-based classification for local dev
    if any(w in query_lower for w in ["compare", "vs", "versus", "better"]):
        category = "comparison"
    elif any(w in query_lower for w in ["risk", "drawdown", "volatility", "stop-loss", "position size"]):
        category = "risk_assessment"
    elif any(w in query_lower for w in ["price", "quote", "current", "how much"]) and not any(
        w in query_lower for w in ["analysis", "debate", "recommend", "should"]
    ):
        category = "price_check"
    elif any(w in query_lower for w in ["market", "sector", "overview", "index", "vn30"]) and not ticker:
        category = "market_overview"
    else:
        category = "stock_analysis"

    return {**state, "category": category, "ticker": ticker}


def route_after_classify(state: DebateState) -> str:
    """Conditional edge: route to the correct workflow based on category."""
    category = state.get("category", "stock_analysis")
    routing = {
        "stock_analysis": "run_debate",
        "price_check": "quick_price",
        "comparison": "compare_stocks",
        "risk_assessment": "risk_assess",
        "market_overview": "market_overview",
    }
    return routing.get(category, "run_debate")


def run_debate(state: DebateState) -> DebateState:
    """Core debate node: execute the full multi-agent debate loop."""
    engine = DebateEngine()
    try:
        result = engine.debate(
            ticker=state["ticker"],
            timeframe=state.get("timeframe", "3 months"),
            min_rounds=state.get("min_rounds", 1),
            max_rounds=state.get("max_rounds", 5),
            mode=state.get("mode", DEBATE_MODE_AUTO),
            human_input=state.get("human_input"),
        )
        return {
            **state,
            "rounds": result.get("rounds", []),
            "status": result.get("status", "completed"),
            "result": result,
        }
    except ValueError as e:
        return {**state, "status": "error", "error": str(e), "result": {}}


def quick_price(state: DebateState) -> DebateState:
    """Quick price check node: return current price and basic metrics."""
    loader = DataLoader()
    stock_data = loader.load_stock_data(state["ticker"])

    if "error" in stock_data:
        return {**state, "status": "error", "error": stock_data["error"], "result": {}}

    prices = stock_data.get("ohlc_prices", {}).get("prices", [])
    info = stock_data.get("company_info", {}).get("info", {})

    if not prices:
        return {**state, "status": "error", "error": "No price data", "result": {}}

    latest = prices[-1]
    closes = [p["close"] for p in prices]
    chg_1d = ((closes[-1] - closes[-2]) / closes[-2] * 100) if len(closes) >= 2 else 0

    result = {
        "ticker": state["ticker"],
        "name": info.get("name", state["ticker"]),
        "price": latest["close"],
        "change_1d_pct": round(chg_1d, 2),
        "high": latest["high"],
        "low": latest["low"],
        "volume": latest["volume"],
        "market_cap": info.get("market_cap", 0),
        "sector": info.get("sector", "N/A"),
        "status": "completed",
        "category": "price_check",
    }
    return {**state, "status": "completed", "result": result}


def risk_assess(state: DebateState) -> DebateState:
    """Focused risk assessment without full debate."""
    from src.core.engine import _risk_manager_analysis, _compute_sma, _compute_rsi

    loader = DataLoader()
    stock_data = loader.load_stock_data(state["ticker"])

    if "error" in stock_data:
        return {**state, "status": "error", "error": stock_data["error"], "result": {}}

    risk_r1 = _risk_manager_analysis(state["ticker"], state.get("timeframe", "3 months"), stock_data, 1)
    risk_r2 = _risk_manager_analysis(state["ticker"], state.get("timeframe", "3 months"), stock_data, 2)

    result = {
        "ticker": state["ticker"],
        "timeframe": state.get("timeframe", "3 months"),
        "risk_assessment_round1": risk_r1,
        "risk_assessment_round2": risk_r2,
        "status": "completed",
        "category": "risk_assessment",
    }
    return {**state, "status": "completed", "result": result}


def compare_stocks(state: DebateState) -> DebateState:
    """Compare multiple stocks. Expects comma-separated tickers."""
    tickers_raw = state.get("ticker", "")
    tickers = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]

    if len(tickers) < 2:
        return {**state, "status": "error", "error": "Comparison requires at least 2 tickers (comma-separated)", "result": {}}

    loader = DataLoader()
    comparisons = []
    for ticker in tickers[:5]:  # Max 5 tickers
        stock_data = loader.load_stock_data(ticker)
        if "error" in stock_data:
            comparisons.append({"ticker": ticker, "error": stock_data["error"]})
            continue

        prices = stock_data.get("ohlc_prices", {}).get("prices", [])
        info = stock_data.get("company_info", {}).get("info", {})
        closes = [p["close"] for p in prices] if prices else []

        comparisons.append({
            "ticker": ticker,
            "name": info.get("name", ticker),
            "price": closes[-1] if closes else 0,
            "market_cap": info.get("market_cap", 0),
            "sector": info.get("sector", "N/A"),
            "change_30d_pct": round(
                ((closes[-1] - closes[-21]) / closes[-21] * 100) if len(closes) > 21 else 0, 2
            ),
        })

    result = {
        "tickers": tickers,
        "comparisons": comparisons,
        "status": "completed",
        "category": "comparison",
    }
    return {**state, "status": "completed", "result": result}


def market_overview(state: DebateState) -> DebateState:
    """Broad market overview — summarize top movers from available data."""
    loader = DataLoader()
    data_path = loader.data_path

    if not data_path.exists():
        return {**state, "status": "error", "error": "Data store not found", "result": {}}

    summaries = []
    for ticker_dir in sorted(data_path.iterdir()):
        if not ticker_dir.is_dir():
            continue
        ticker = ticker_dir.name.replace(".VN", "")
        stock_data = loader.load_stock_data(ticker)
        if "error" in stock_data:
            continue
        prices = stock_data.get("ohlc_prices", {}).get("prices", [])
        if not prices:
            continue
        closes = [p["close"] for p in prices]
        chg = ((closes[-1] - closes[-2]) / closes[-2] * 100) if len(closes) >= 2 else 0
        summaries.append({
            "ticker": ticker,
            "price": closes[-1],
            "change_1d_pct": round(chg, 2),
        })

    # Sort by absolute daily change to find top movers
    summaries.sort(key=lambda x: abs(x["change_1d_pct"]), reverse=True)

    result = {
        "total_stocks": len(summaries),
        "top_gainers": [s for s in summaries if s["change_1d_pct"] > 0][:5],
        "top_losers": [s for s in summaries if s["change_1d_pct"] < 0][:5],
        "status": "completed",
        "category": "market_overview",
    }
    return {**state, "status": "completed", "result": result}


def check_human_loop(state: DebateState) -> str:
    """After debate, decide if we go to END or wait for human."""
    if state.get("status") == "awaiting_human_input":
        return "await_human"
    return "finalize"


def finalize(state: DebateState) -> DebateState:
    """Terminal node — pass through result."""
    return state


def await_human(state: DebateState) -> DebateState:
    """Placeholder for human-in-loop checkpoint.
    
    In production with LangGraph checkpointing, this node would pause
    execution and wait for external input via the checkpoint API.
    For local dev, the /continue endpoint handles this.
    """
    return state


# ── Graph construction ────────────────────────────────────────

def build_debate_graph() -> StateGraph:
    """Build and compile the LangGraph debate workflow.
    
    Graph topology:
    
        START → classify → (route)
                              ├─ run_debate → (check_human_loop)
                              │                 ├─ finalize → END
                              │                 └─ await_human → END
                              ├─ quick_price → END
                              ├─ risk_assess → END
                              ├─ compare_stocks → END
                              └─ market_overview → END
    """
    graph = StateGraph(DebateState)

    # Add nodes
    graph.add_node("classify", classify_query)
    graph.add_node("run_debate", run_debate)
    graph.add_node("quick_price", quick_price)
    graph.add_node("risk_assess", risk_assess)
    graph.add_node("compare_stocks", compare_stocks)
    graph.add_node("market_overview", market_overview)
    graph.add_node("finalize", finalize)
    graph.add_node("await_human", await_human)

    # Entry edge
    graph.add_edge(START, "classify")

    # Conditional routing from classifier
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "run_debate": "run_debate",
            "quick_price": "quick_price",
            "risk_assess": "risk_assess",
            "compare_stocks": "compare_stocks",
            "market_overview": "market_overview",
        },
    )

    # After debate, check if human-in-loop is needed
    graph.add_conditional_edges(
        "run_debate",
        check_human_loop,
        {
            "finalize": "finalize",
            "await_human": "await_human",
        },
    )

    # Terminal edges
    graph.add_edge("quick_price", END)
    graph.add_edge("risk_assess", END)
    graph.add_edge("compare_stocks", END)
    graph.add_edge("market_overview", END)
    graph.add_edge("finalize", END)
    graph.add_edge("await_human", END)

    return graph.compile()


# Lazy-loaded compiled graph instance (compiled on first use, not at import time)
_debate_graph_instance = None


def get_debate_graph():
    """Get or lazily compile the debate graph.
    
    This defers graph compilation until first use, avoiding import failures
    if the graph compilation encounters issues.
    """
    global _debate_graph_instance
    if _debate_graph_instance is None:
        try:
            _debate_graph_instance = build_debate_graph()
        except Exception as e:
            raise RuntimeError(f"Failed to compile LangGraph debate orchestrator: {e}")
    return _debate_graph_instance


def run_graph(
    ticker: str,
    timeframe: str = "3 months",
    min_rounds: int = 1,
    max_rounds: int = 5,
    mode: str = DEBATE_MODE_AUTO,
    query: str = "",
    human_input: str | None = None,
) -> dict[str, Any]:
    """Execute the LangGraph debate workflow.
    
    Args:
        ticker: Stock ticker symbol (or comma-separated for comparison)
        timeframe: Investment timeframe
        min_rounds: Minimum debate rounds
        max_rounds: Maximum debate rounds
        mode: "auto" or "human"
        query: Natural language query for classifier routing
        human_input: Human feedback for human-in-loop mode
    
    Returns:
        Complete result dict from the graph execution
    """
    initial_state: DebateState = {
        "query": query or f"analyze {ticker}",
        "ticker": ticker,
        "timeframe": timeframe,
        "min_rounds": min_rounds,
        "max_rounds": max_rounds,
        "mode": mode,
        "human_input": human_input,
        "category": "",
        "rounds": [],
        "current_round": 0,
        "should_continue": True,
        "status": "",
        "result": {},
        "error": "",
    }

    final_state = get_debate_graph().invoke(initial_state)
    return final_state.get("result", final_state)
