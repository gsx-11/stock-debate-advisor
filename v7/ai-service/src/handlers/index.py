"""AWS Lambda handler for Stock Debate API v3.0
Routes: /health, /api/v1/debate/start, /api/v1/debate/status/{id},
        /api/v1/debate/result/{id}, /api/v1/companies, /api/v1/company/{symbol},
        /api/v2/query (LangGraph)
"""
import json
import os
import uuid
import re
from datetime import datetime, timezone
from typing import Any, Dict
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

if os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    from src.core.engine_bedrock import DebateEngineBedrock as EngineClass
else:
    from src.core.engine import DebateEngine as EngineClass

engine = None
_sessions: dict[str, dict] = {}


def _get_engine():
    global engine
    if engine is None:
        engine = EngineClass()
    return engine


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    method = event.get('httpMethod', 'GET').upper()
    raw_path = event.get('path', '/')
    # Strip API Gateway stage prefix (e.g. /prod)
    path = re.sub(r'^/prod', '', raw_path)

    try:
        # Health
        if path == '/health' and method == 'GET':
            return success_response({'status': 'healthy', 'version': '3.0'})

        # Debate start
        if path == '/api/v1/debate/start' and method == 'POST':
            return _handle_debate_start(event)

        # Debate status polling
        m = re.match(r'^/api/v1/debate/status/(.+)$', path)
        if m and method == 'GET':
            return _handle_debate_status(m.group(1))

        # Debate result
        m = re.match(r'^/api/v1/debate/result/(.+)$', path)
        if m and method == 'GET':
            return _handle_debate_result(m.group(1))

        # Debate continue (human-in-loop)
        if path == '/api/v1/debate/continue' and method == 'POST':
            return _handle_debate_continue(event)

        # Companies list
        if path == '/api/v1/companies' and method == 'GET':
            return _handle_list_companies()

        # Company data
        m = re.match(r'^/api/v1/company/(.+)$', path)
        if m and method == 'GET':
            return _handle_company_data(m.group(1))

        # LangGraph query
        if path == '/api/v2/query' and method == 'POST':
            return _handle_langgraph_query(event)

        # Legacy /debate endpoint (backward compat)
        if path == '/debate' and method == 'POST':
            return _handle_debate_start(event)

        return error_response(404, {'error': f'Route {method} {path} not found'})
    except Exception as e:
        return error_response(500, {'error': str(e)})


def _handle_debate_start(event: Dict[str, Any]) -> Dict[str, Any]:
    body = json.loads(event.get('body', '{}'))
    ticker = body.get('ticker', '').upper().strip()
    timeframe = body.get('timeframe', '3 months')
    min_rounds = int(body.get('min_rounds', 1))
    max_rounds = int(body.get('max_rounds', 5))
    mode = body.get('mode', 'auto')

    if not ticker or len(ticker) < 2:
        return error_response(400, {'error': 'Invalid ticker'})
    if min_rounds < 1 or max_rounds < min_rounds or max_rounds > 10:
        return error_response(400, {'error': 'Invalid round configuration'})

    session_id = f"debate_{uuid.uuid4().hex[:12]}"
    _sessions[session_id] = {
        'session_id': session_id, 'symbol': ticker, 'status': 'in_progress',
        'created_at': datetime.now(timezone.utc).isoformat(),
    }

    eng = _get_engine()
    result = eng.debate(ticker, timeframe, min_rounds, max_rounds, mode=mode)
    result['session_id'] = session_id

    _sessions[session_id] = {
        'session_id': session_id, 'symbol': ticker,
        'status': result.get('status', 'completed'),
        'progress': 100 if result.get('status') == 'completed' else 50,
        'created_at': _sessions[session_id]['created_at'],
        'completed_at': datetime.now(timezone.utc).isoformat(),
        'result': result,
    }

    return success_response(result)


def _handle_debate_continue(event: Dict[str, Any]) -> Dict[str, Any]:
    body = json.loads(event.get('body', '{}'))
    ticker = body.get('ticker', '').upper().strip()
    timeframe = body.get('timeframe', '3 months')
    human_input = body.get('human_input', '')
    min_rounds = int(body.get('min_rounds', 1))
    max_rounds = int(body.get('max_rounds', 5))

    if not ticker or not human_input:
        return error_response(400, {'error': 'ticker and human_input are required'})

    eng = _get_engine()
    result = eng.debate(ticker, timeframe, min_rounds, max_rounds, mode='human', human_input=human_input)
    return success_response(result)


def _handle_debate_status(session_id: str) -> Dict[str, Any]:
    session = _sessions.get(session_id)
    if not session:
        return error_response(404, {'error': f'Session {session_id} not found'})
    return success_response({
        'session_id': session['session_id'],
        'symbol': session['symbol'],
        'status': session['status'],
        'progress': session.get('progress', 0),
    })


def _handle_debate_result(session_id: str) -> Dict[str, Any]:
    session = _sessions.get(session_id)
    if not session:
        return error_response(404, {'error': f'Session {session_id} not found'})
    if session['status'] != 'completed':
        return error_response(409, {'error': f'Debate not completed, status: {session["status"]}'})
    return success_response(session.get('result', {}))


def _handle_list_companies() -> Dict[str, Any]:
    from src.core.config import settings
    data_path = settings.DATA_STORE_PATH
    if data_path.exists():
        symbols = sorted(d.name.replace('.VN', '') for d in data_path.iterdir() if d.is_dir())
    else:
        symbols = []
    return success_response({'symbols': symbols, 'count': len(symbols)})


def _handle_company_data(symbol: str) -> Dict[str, Any]:
    eng = _get_engine()
    if hasattr(eng, 'data_loader'):
        data = eng.data_loader.load_stock_data(symbol)
    else:
        data = {}
    return success_response({
        'symbol': symbol,
        'company': data.get('company_info', {}),
        'financial': data.get('financial_reports', {}),
        'prices': data.get('ohlc_prices', {}),
    })


def _handle_langgraph_query(event: Dict[str, Any]) -> Dict[str, Any]:
    from src.core.langgraph_orchestrator import run_graph
    body = json.loads(event.get('body', '{}'))
    result = run_graph(
        ticker=body.get('ticker', ''),
        timeframe=body.get('timeframe', '3 months'),
        min_rounds=int(body.get('min_rounds', 1)),
        max_rounds=int(body.get('max_rounds', 5)),
        mode=body.get('mode', 'auto'),
        query=body.get('query', ''),
        human_input=body.get('human_input'),
    )
    return success_response(result)


def health_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    return success_response({'status': 'healthy', 'version': '3.0'})


def success_response(data: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
        },
        'body': json.dumps(data, default=str)
    }


def error_response(status_code: int, error: Dict[str, str]) -> Dict[str, Any]:
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
        },
        'body': json.dumps(error)
    }
