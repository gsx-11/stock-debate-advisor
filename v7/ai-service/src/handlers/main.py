from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys
import os
import uuid
import asyncio
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.core.config import settings
from src.utils.models import DebateRequest, DebateContinueRequest, DebateResponse, HealthResponse
from src.core.engine import DebateEngine
from src.core.langgraph_orchestrator import run_graph

logging.basicConfig(level=logging.INFO if settings.VERBOSE else logging.WARNING)
logger = logging.getLogger(__name__)

engine = None
# In-memory session store for local dev (production uses DynamoDB via backend)
_sessions: dict[str, dict] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    logger.info("Starting AI Service...")
    settings.validate()
    engine = DebateEngine()
    logger.info("Engine initialized")
    yield
    logger.info("Shutting down AI Service...")

app = FastAPI(
    title="Stock Debate Advisor API",
    description="Multi-agent stock analysis debate system with Auto/Human-in-loop modes",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="healthy", version="3.0")

async def _handle_debate_request(request: DebateRequest) -> DebateResponse:
    """Shared logic for debate endpoints. Stores result in session store."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    session_id = f"debate_{uuid.uuid4().hex[:12]}"
    _sessions[session_id] = {
        "session_id": session_id,
        "symbol": request.ticker,
        "status": "in_progress",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result = engine.debate(
            request.ticker,
            request.timeframe,
            request.min_rounds,
            request.max_rounds,
            mode=request.mode,
        )
        
        response = DebateResponse(
            session_id=session_id,
            ticker=request.ticker,
            timeframe=request.timeframe,
            actual_rounds=result["actual_rounds"],
            rounds=result["rounds"],
            mode=result.get("mode", "auto"),
            status=result.get("status", "completed"),
            final_recommendation=result["final_recommendation"],
            confidence=result["confidence"],
            confidence_percent=result.get("confidence_percent", 0.0),
            decision_qualified=result.get("decision_qualified", False),
            rationale=result["rationale"],
            risks=result["risks"],
            monitor=result["monitor"],
            price_target=result.get("price_target", ""),
        )

        _sessions[session_id] = {
            "session_id": session_id,
            "symbol": request.ticker,
            "status": response.status,
            "progress": 100 if response.status == "completed" else 50,
            "created_at": _sessions[session_id]["created_at"],
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result": response.model_dump(),
        }

        return response
    except Exception as e:
        logger.error(f"Debate error: {e}")
        _sessions[session_id]["status"] = "failed"
        _sessions[session_id]["error"] = str(e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/debate", response_model=DebateResponse)
async def start_debate(request: DebateRequest):
    """Legacy endpoint for backward compatibility"""
    return await _handle_debate_request(request)

@app.post("/api/v1/debate/start", response_model=DebateResponse)
async def start_debate_v1(request: DebateRequest):
    """API v1 endpoint - matches frontend expectation.
    
    Modes:
    - auto: 5 agents (fundamental, technical, sentiment, risk_manager, judge) debate automatically until verdict
    - human: agents debate one round, then pause for human input via /continue endpoint
    """
    return await _handle_debate_request(request)

@app.post("/api/v1/debate/continue", response_model=DebateResponse)
async def continue_debate(request: DebateContinueRequest):
    """Continue a human-in-loop debate with human feedback.
    
    Called after receiving an 'awaiting_human_input' status from /start with mode='human'.
    The human_input field carries the admin/requester's direction for the next round.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    # Look up the paused session
    session = _sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {request.session_id}")
    
    if session.get("status") != "awaiting_human_input":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot continue debate. Current status: {session.get('status')}. Only 'awaiting_human_input' sessions can be continued."
        )
    
    if not request.human_input or request.human_input.strip() == "":
        raise HTTPException(status_code=400, detail="human_input cannot be empty")
    
    try:
        # Continue the debate with human feedback
        result = engine.debate(
            request.ticker,
            request.timeframe,
            request.min_rounds,
            request.max_rounds,
            mode="human",
            human_input=request.human_input,
        )
        
        response = DebateResponse(
            session_id=request.session_id,
            ticker=request.ticker,
            timeframe=request.timeframe,
            actual_rounds=result["actual_rounds"],
            rounds=result["rounds"],
            mode="human",
            status=result.get("status", "completed"),
            final_recommendation=result["final_recommendation"],
            confidence=result["confidence"],
            confidence_percent=result.get("confidence_percent", 0.0),
            decision_qualified=result.get("decision_qualified", False),
            rationale=result["rationale"],
            risks=result["risks"],
            monitor=result["monitor"],
            price_target=result.get("price_target", ""),
        )
        
        # Update session state
        _sessions[request.session_id] = {
            "session_id": request.session_id,
            "symbol": request.ticker,
            "status": response.status,
            "progress": 100 if response.status == "completed" else 50,
            "created_at": session["created_at"],
            "resumed_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat() if response.status == "completed" else None,
            "result": response.model_dump(),
        }
        
        return response
    except Exception as e:
        logger.error(f"Continue debate error: {e}")
        _sessions[request.session_id]["status"] = "failed"
        _sessions[request.session_id]["error"] = str(e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Session polling endpoints (used by frontend) ─────────────

@app.get("/api/v1/debate/status/{session_id}")
async def debate_status(session_id: str) -> dict:
    """Get debate session status. Frontend polls this after /start."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {
        "session_id": session["session_id"],
        "symbol": session["symbol"],
        "status": session["status"],
        "progress": session.get("progress", 0),
    }

@app.get("/api/v1/debate/result/{session_id}")
async def debate_result(session_id: str) -> dict:
    """Get completed debate result. Frontend calls after status=completed."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if session["status"] != "completed":
        raise HTTPException(status_code=409, detail=f"Debate not completed, status: {session['status']}")
    return session.get("result", {})

@app.get("/api/v1/companies")
async def list_companies() -> dict:
    """List available stock symbols from data store."""
    try:
        data_path = settings.DATA_STORE_PATH
        symbols = sorted(
            d.name.replace(".VN", "")
            for d in data_path.iterdir()
            if d.is_dir()
        )
        return {"symbols": symbols, "count": len(symbols)}
    except Exception as e:
        logger.error(f"List companies error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/debate/history")
async def debate_history(limit: int = 20) -> dict:
    """Return most-recent completed debate sessions (newest first)."""
    completed = [
        {
            "symbol": s["symbol"],
            "verdict": s["result"].get("final_recommendation", "HOLD").upper(),
            "confidence": _parse_confidence_pct(s["result"].get("confidence", "50%")),
            "timestamp": int(
                datetime.fromisoformat(
                    s.get("completed_at") or s.get("created_at", datetime.now(timezone.utc).isoformat())
                ).timestamp()
                * 1000
            ),
        }
        for s in _sessions.values()
        if s.get("status") == "completed" and s.get("result")
    ]
    completed.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"debates": completed[:limit]}

def _parse_confidence_pct(raw: str | float | int) -> int:
    """Convert confidence string like '85%' or float 0.85 to integer 0-100."""
    if isinstance(raw, (int, float)):
        return int(raw * 100) if raw <= 1 else int(raw)
    import re
    m = re.search(r"[\d.]+", str(raw))
    val = float(m.group()) if m else 50.0
    return int(val) if val > 1 else int(val * 100)

@app.get("/api/v1/company/{symbol}")
async def get_company_data(symbol: str) -> dict:
    """Get company data (info + financial + prices) from data store."""
    try:
        from src.core.engine import DataLoader
        loader = DataLoader()
        data = loader.load_stock_data(symbol)
        return {
            "symbol": symbol,
            "company": data.get("company_info", {}),
            "financial": data.get("financial_reports", {}),
            "prices": data.get("ohlc_prices", {}),
        }
    except Exception as e:
        logger.error(f"Get company data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── WebSocket streaming endpoint ─────────────────────────────

@app.websocket("/ws/debate/stream")
async def debate_stream(websocket: WebSocket) -> None:
    """Stream a multi-round debate turn-by-turn over WebSocket.

    Client sends one JSON message with debate params, then receives a
    sequence of events: session_started → round_started → turn (per role)
    → round_completed → session_completed (or error).

    Event shape: {"event": "<type>", ...fields}
    Roles emitted per round: moderator, fundamental, technical, sentiment,
    risk_manager, judge, moderator (transition/closing).
    """
    await websocket.accept()

    async def send(event: dict) -> None:
        await websocket.send_json(event)

    try:
        data = await websocket.receive_json()
        ticker: str = str(data.get("ticker", "")).strip().upper()
        timeframe: str = str(data.get("timeframe", "3 months"))
        min_rounds: int = max(1, int(data.get("min_rounds", 1)))
        max_rounds: int = min(10, max(1, int(data.get("max_rounds", 5))))
        mode: str = str(data.get("mode", "auto"))

        if not ticker:
            await send({"event": "error", "message": "ticker is required"})
            return

        if not engine:
            await send({"event": "error", "message": "Engine not initialized"})
            return

        session_id = f"debate_{uuid.uuid4().hex[:12]}"
        await send({
            "event": "session_started",
            "session_id": session_id,
            "ticker": ticker,
            "timeframe": timeframe,
        })

        stock_data = await asyncio.to_thread(engine.data_loader.load_stock_data, ticker)
        if "error" in stock_data:
            await send({"event": "error", "message": stock_data["error"]})
            return

        from src.core.engine import (
            _fundamental_analysis,
            _technical_analysis,
            _sentiment_analysis,
            _risk_manager_analysis,
            _judge_analysis,
            _parse_confidence_percent,
            _confidence_meets_threshold,
        )

        analyst_fns = [
            ("fundamental", _fundamental_analysis),
            ("technical", _technical_analysis),
            ("sentiment", _sentiment_analysis),
            ("risk_manager", _risk_manager_analysis),
        ]

        rounds_data: list = []
        current_round = 1
        should_continue = True

        while should_continue and current_round <= max_rounds:
            await send({"event": "round_started", "round": current_round, "max_rounds": max_rounds})

            # Moderator opening
            await send({
                "event": "turn",
                "role": "moderator",
                "round": current_round,
                "content": (
                    f"Round {current_round} of up to {max_rounds}. "
                    f"Analysts, please present your analysis for {ticker} ({timeframe} timeframe)."
                ),
            })

            responses: dict = {}
            for role, fn in analyst_fns:
                analysis = await asyncio.to_thread(fn, ticker, timeframe, stock_data, current_round)
                responses[role] = analysis
                await send({"event": "turn", "role": role, "round": current_round, "content": analysis})

            # Judge turn
            judge_output = await asyncio.to_thread(
                _judge_analysis, ticker, timeframe, current_round, max_rounds, responses, stock_data
            )
            await send({"event": "turn", "role": "judge", "round": current_round, "content": judge_output})

            confidence_pct = _parse_confidence_percent(judge_output)
            confidence_qualified = _confidence_meets_threshold(confidence_pct)

            round_data = {"round_num": current_round, **responses, "judge_decision": judge_output}
            rounds_data.append(round_data)

            await send({
                "event": "round_completed",
                "round": current_round,
                "confidence_percent": confidence_pct,
                "decision_qualified": confidence_qualified,
            })

            wants_continue = "CONTINUE" in judge_output
            below_threshold = not confidence_qualified
            should_continue = (
                (wants_continue and current_round < max_rounds)
                or (current_round < min_rounds)
                or (below_threshold and current_round < max_rounds)
            )

            # Moderator transition or closing
            if should_continue:
                await send({
                    "event": "turn",
                    "role": "moderator",
                    "round": current_round,
                    "content": (
                        f"Confidence at {confidence_pct:.0f}% — proceeding to "
                        f"Round {current_round + 1} for stronger consensus."
                    ),
                })
            elif not confidence_qualified:
                await send({
                    "event": "turn",
                    "role": "moderator",
                    "round": current_round,
                    "content": (
                        f"After {current_round} round(s), confidence is {confidence_pct:.0f}% — "
                        "below the 80% threshold. A final verdict cannot be issued. "
                        "More data or clarity is recommended before deciding."
                    ),
                })
            else:
                await send({
                    "event": "turn",
                    "role": "moderator",
                    "round": current_round,
                    "content": (
                        f"Debate concluded with {confidence_pct:.0f}% confidence after "
                        f"{current_round} round(s). Judge's verdict has been issued."
                    ),
                })

            current_round += 1

        final_verdict = engine._extract_final_verdict(rounds_data[-1]["judge_decision"])
        final_conf_pct = final_verdict.get("confidence_percent", 0.0)
        final_qualified = final_verdict.get("decision_qualified", False)

        await send({
            "event": "session_completed",
            "session_id": session_id,
            "final_recommendation": final_verdict.get("recommendation", "NO_DECISION"),
            "confidence": final_verdict.get("confidence", "Low"),
            "confidence_percent": final_conf_pct,
            "decision_qualified": final_qualified,
            "rationale": final_verdict.get("reasoning", ""),
            "risks": final_verdict.get("risks", ""),
            "monitor": final_verdict.get("monitor", ""),
            "price_target": final_verdict.get("price_target", ""),
            "actual_rounds": current_round - 1,
        })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from debate stream")
    except Exception as exc:
        logger.error(f"WebSocket debate stream error: {exc}")
        try:
            await send({"event": "error", "message": str(exc)})
        except Exception:
            pass


# ── LangGraph orchestrator endpoints ──────────────────────────
from pydantic import BaseModel, Field
from typing import Any

class GraphQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query — the classifier routes it")
    ticker: str = Field(default="", description="Stock ticker (or comma-separated for comparison)")
    timeframe: str = Field(default="3 months")
    min_rounds: int = Field(default=1, ge=1, le=5)
    max_rounds: int = Field(default=5, ge=1, le=10)
    mode: str = Field(default="auto", description="auto or human")
    human_input: str | None = Field(default=None, description="Human feedback for human-in-loop")

@app.post("/api/v2/query")
async def langgraph_query(request: GraphQueryRequest) -> dict[str, Any]:
    """LangGraph-powered query endpoint with intelligent routing.
    
    The classifier node analyzes the query and routes to:
    - stock_analysis: Full multi-agent debate
    - price_check: Quick price lookup  
    - comparison: Side-by-side stock comparison
    - risk_assessment: Focused risk analysis
    - market_overview: Broad market summary
    """
    try:
        result = run_graph(
            ticker=request.ticker,
            timeframe=request.timeframe,
            min_rounds=request.min_rounds,
            max_rounds=request.max_rounds,
            mode=request.mode,
            query=request.query,
            human_input=request.human_input,
        )
        return result
    except Exception as e:
        logger.error(f"LangGraph query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
