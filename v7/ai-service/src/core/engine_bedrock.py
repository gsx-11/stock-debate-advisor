"""AWS Bedrock-powered debate engine for Stock Debate Advisor v3.0 using Claude Sonnet 3.5
Features: 5 agents (fundamental, technical, sentiment, risk_manager, judge),
          price conditions, Auto/Human-in-loop mode.
"""
from typing import Dict, Any
import json
import os
import sys
import boto3
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.core.constants import AGENT_PROMPTS, AUTO_MODE_AGENTS
from src.core.config import settings
from src.core.engine import _parse_confidence_percent, _confidence_meets_threshold

class DataLoaderDynamoDB:
    """Load stock data from DynamoDB tables"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.companies_table = self.dynamodb.Table(os.environ.get('COMPANIES_TABLE', settings.COMPANIES_TABLE))
        self.financial_table = self.dynamodb.Table(os.environ.get('FINANCIAL_REPORTS_TABLE', settings.FINANCIAL_REPORTS_TABLE))
        self.ohlc_table = self.dynamodb.Table(os.environ.get('OHLC_PRICES_TABLE', settings.OHLC_PRICES_TABLE))
    
    def load_stock_data(self, ticker: str) -> Dict[str, Any]:
        try:
            company_response = self.companies_table.get_item(Key={'ticker': ticker})
            company_data = company_response.get('Item', {})
            
            if not company_data:
                return {'error': f'No data found for {ticker}'}
            
            financial_response = self.financial_table.query(
                KeyConditionExpression='ticker = :ticker',
                ExpressionAttributeValues={':ticker': ticker},
                ScanIndexForward=False,
                Limit=4
            )
            financial_data = financial_response.get('Items', [])
            
            ohlc_response = self.ohlc_table.query(
                KeyConditionExpression='ticker = :ticker',
                ExpressionAttributeValues={':ticker': ticker},
                ScanIndexForward=False,
                Limit=60
            )
            ohlc_data = ohlc_response.get('Items', [])
            
            return {
                'company_info': company_data,
                'financial_reports': financial_data,
                'ohlc_prices': {'prices': ohlc_data}
            }
        
        except Exception as e:
            return {'error': f'Failed to load data from DynamoDB: {str(e)}'}


class DebateEngineBedrock:
    """Multi-agent debate engine using Amazon Bedrock with Claude Sonnet 3.5"""
    
    def __init__(self):
        self.bedrock = boto3.client('bedrock-runtime', region_name=settings.BEDROCK_REGION)
        self.model_id = settings.BEDROCK_MODEL  # Claude Sonnet 3.5: anthropic.claude-3-5-sonnet-20241022-v2:0
        self.data_loader = DataLoaderDynamoDB()
        self.debate_history = []
    
    def _call_bedrock(self, prompt: str) -> str:
        """Call Claude Sonnet 3.5 via Bedrock"""
        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                contentType='application/json',
                accept='application/json',
                body=json.dumps({
                    'anthropic_version': 'bedrock-2023-06-01',
                    'max_tokens': settings.MAX_TOKENS,
                    'messages': [
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ],
                    'temperature': settings.TEMPERATURE
                })
            )
            
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']
        
        except Exception as e:
            return f"Error calling Bedrock: {str(e)}"
    
    def debate(self, ticker: str, timeframe: str, min_rounds: int, max_rounds: int,
               mode: str = "auto", human_input: str | None = None) -> Dict[str, Any]:
        """Execute iterative debate with Judge control. Supports auto and human-in-loop modes."""
        stock_data = self.data_loader.load_stock_data(ticker)
        if 'error' in stock_data:
            raise ValueError(stock_data['error'])
        
        rounds_data = []
        current_round = 1
        should_continue = True
        
        while should_continue and current_round <= max_rounds:
            round_result = self._run_debate_round(ticker, timeframe, current_round, stock_data)

            if mode == "human" and human_input:
                round_result['human_input'] = human_input

            rounds_data.append(round_result)
            
            # In human mode, pause after first round for human input
            if mode == "human" and current_round >= 1 and not human_input:
                return {
                    'ticker': ticker,
                    'timeframe': timeframe,
                    'actual_rounds': current_round,
                    'rounds': rounds_data,
                    'mode': 'human',
                    'status': 'awaiting_human_input',
                    'final_recommendation': 'PENDING',
                    'confidence': 'N/A',
                    'rationale': 'Awaiting human input to continue debate.',
                    'risks': '',
                    'monitor': '',
                    'price_target': '',
                }

            judge_decision = round_result.get('judge_decision', '')
            confidence_pct = _parse_confidence_percent(judge_decision)
            confidence_qualified = _confidence_meets_threshold(confidence_pct)

            # In human mode, pause after first round for human input
            if mode == "human" and current_round >= 1 and not human_input:
                return {
                    'ticker': ticker, 'timeframe': timeframe,
                    'actual_rounds': current_round, 'rounds': rounds_data,
                    'mode': 'human', 'status': 'awaiting_human_input',
                    'final_recommendation': 'PENDING', 'confidence': 'N/A',
                    'confidence_percent': confidence_pct, 'decision_qualified': False,
                    'rationale': 'Awaiting human input to continue debate.',
                    'risks': '', 'monitor': '', 'price_target': '',
                }

            # Continue when: judge asks, min_rounds not met, or threshold not met
            wants_continue = 'CONTINUE' in judge_decision
            below_threshold = not confidence_qualified
            should_continue = (
                (wants_continue and current_round < max_rounds)
                or (current_round < min_rounds)
                or (below_threshold and current_round < max_rounds)
            )

            current_round += 1
        
        final_verdict = self._extract_final_verdict(rounds_data[-1]['judge_decision'])
        
        self._cache_debate_result(ticker, timeframe, rounds_data, final_verdict)
        
        final_recommendation = final_verdict.get('recommendation', 'NO_DECISION')
        final_confidence_pct = final_verdict.get('confidence_percent', 0.0)
        final_qualified = final_verdict.get('decision_qualified', False)

        return {
            'ticker': ticker,
            'timeframe': timeframe,
            'actual_rounds': current_round - 1,
            'rounds': rounds_data,
            'mode': mode,
            'status': 'completed' if final_qualified else 'no_decision',
            'final_recommendation': final_recommendation,
            'confidence': final_verdict.get('confidence', 'Low'),
            'confidence_percent': final_confidence_pct,
            'decision_qualified': final_qualified,
            'rationale': final_verdict.get('reasoning', ''),
            'risks': final_verdict.get('risks', ''),
            'monitor': final_verdict.get('monitor', ''),
            'price_target': final_verdict.get('price_target', ''),
        }
    
    def _run_debate_round(self, ticker: str, timeframe: str, round_num: int, stock_data: Dict) -> Dict[str, str]:
        """Execute single debate round with all 5 analysts (fundamental, technical, sentiment, risk_manager) + judge"""
        context = f"Analyzing {ticker} for {timeframe} timeframe. Round {round_num}."
        history_context = "\n".join(self.debate_history[-3:]) if self.debate_history else ""
        
        responses = {}
        for analyst in AUTO_MODE_AGENTS:
            prompt = (
                f"{AGENT_PROMPTS[analyst]}\n\n{context}\n\nPrevious discussion:\n{history_context}\n\n"
                f"Provide your {analyst} analysis with specific data points, price conditions "
                f"(BUY below X / SELL above Y / HOLD at X-Y), and recommendation for {timeframe} timeframe."
            )
            result = self._call_bedrock(prompt)
            responses[analyst] = result
            self.debate_history.append(f"Round {round_num} {analyst.upper()}: {result[:200]}")
        
        judge_prompt = (
            f"{AGENT_PROMPTS['judge']}\n\nRound {round_num} Debate Summary:\n"
            + "\n".join([f"{k}: {v[:150]}" for k, v in responses.items()])
            + f"\n\nEvaluate the debate quality. All agents must include price conditions. "
            f"Decide: CONTINUE (if more analysis needed) or CONCLUDE (if sufficient evidence) "
            f"for {timeframe} timeframe investment decision.\n\nRespond with CONTINUE or CONCLUDE "
            f"followed by your reasoning, recommendation (BUY/HOLD/SELL), and price target."
        )
        
        judge_result = self._call_bedrock(judge_prompt)
        
        return {
            'round_num': round_num,
            'fundamental': responses.get('fundamental', ''),
            'technical': responses.get('technical', ''),
            'sentiment': responses.get('sentiment', ''),
            'risk_manager': responses.get('risk_manager', ''),
            'judge_decision': judge_result,
            'human_input': None,
        }
    
    def _extract_final_verdict(self, judge_output: str) -> Dict[str, str]:
        """Parse final investment verdict from judge decision"""
        lines = judge_output.split("\n")
        confidence_pct = _parse_confidence_percent(judge_output)
        qualified = _confidence_meets_threshold(confidence_pct)

        verdict = {
            'recommendation': 'HOLD',
            'confidence': 'High' if confidence_pct > 80 else 'Medium' if confidence_pct > 50 else 'Low',
            'confidence_percent': confidence_pct,
            'decision_qualified': qualified,
            'reasoning': judge_output[:300],
            'risks': '',
            'monitor': '',
            'price_target': '',
        }

        if judge_output.lstrip().startswith('NO_DECISION'):
            verdict['recommendation'] = 'NO_DECISION'
            verdict['decision_qualified'] = False
            return verdict

        for line in lines:
            line_lower = line.lower()
            if "buy" in line_lower and ("for" in line_lower or "below" in line_lower):
                verdict['recommendation'] = 'BUY'
            elif "sell" in line_lower and ("for" in line_lower or "above" in line_lower):
                verdict['recommendation'] = 'SELL'
            elif "risk" in line_lower:
                verdict['risks'] = line.replace("Risk:", "").strip()
            elif "monitor" in line_lower:
                verdict['monitor'] = line.replace("Monitor:", "").strip()
            elif "price target" in line_lower or "target price" in line_lower:
                verdict['price_target'] = line.strip()

        return verdict
    
    def _cache_debate_result(self, ticker: str, timeframe: str, rounds: list, verdict: dict):
        """Cache debate result in DynamoDB for future lookups"""
        try:
            dynamodb = boto3.resource('dynamodb')
            debate_table = dynamodb.Table(os.environ.get('DEBATE_RESULTS_TABLE', settings.DEBATE_RESULTS_TABLE))
            
            timestamp = datetime.utcnow().isoformat()
            
            debate_table.put_item(
                Item={
                    'pk': f"{ticker}#{timeframe}",
                    'sk': timestamp,
                    'created_at': timestamp,
                    'ticker': ticker,
                    'timeframe': timeframe,
                    'rounds': len(rounds),
                    'recommendation': verdict.get('recommendation', 'HOLD'),
                    'confidence': verdict.get('confidence', 'Medium'),
                    'rationale': verdict.get('reasoning', '')[:500],
                    'ttl': int(datetime.utcnow().timestamp()) + (7 * 24 * 60 * 60)  # 7 day TTL
                }
            )
        except Exception as e:
            print(f"Failed to cache debate result: {e}")
