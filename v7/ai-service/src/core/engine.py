"""
Local debate engine for development (file-based data).
Produces data-driven analysis from real stock data.
For Lambda/AWS environment, use engine_bedrock.py instead.
"""
from typing import Dict, Any, List
import json
from pathlib import Path
import sys
import os
import math

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.core.config import settings
from src.core.constants import (
    AGENT_PROMPTS,
    DEBATE_MODE_AUTO,
    DEBATE_MODE_HUMAN,
    AUTO_MODE_AGENTS,
    QUERY_CATEGORIES,
)

# ── Confidence threshold ──────────────────────────────────────
_CONFIDENCE_THRESHOLD: float = 80.0


def _parse_confidence_percent(text: str) -> float:
    """Extract numeric confidence percentage from judge output text.

    Recognises patterns like '85%', '**Confidence:** 85%', or falls back
    to categorical labels (High → 85, Medium → 55, Low → 20).
    """
    import re
    m = re.search(r'\b(\d{1,3}(?:\.\d+)?)\s*%', text, re.IGNORECASE)
    if m:
        val = float(m.group(1))
        return min(max(val, 0.0), 100.0)
    lower = text.lower()
    if 'high' in lower:
        return 85.0
    if 'low' in lower:
        return 20.0
    return 55.0  # Default Medium


def _confidence_meets_threshold(confidence_pct: float) -> bool:
    """Return True only when confidence is *strictly* above 80%."""
    return confidence_pct > _CONFIDENCE_THRESHOLD


def _fmt(value: float, decimals: int = 2) -> str:
    """Format large numbers with B/M/K suffixes."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    abs_val = abs(value)
    if abs_val >= 1e12:
        return f"{value / 1e12:,.{decimals}f}T"
    if abs_val >= 1e9:
        return f"{value / 1e9:,.{decimals}f}B"
    if abs_val >= 1e6:
        return f"{value / 1e6:,.{decimals}f}M"
    if abs_val >= 1e3:
        return f"{value / 1e3:,.{decimals}f}K"
    return f"{value:,.{decimals}f}"


class DataLoader:
    def __init__(self):
        self.data_path = settings.DATA_STORE_PATH

    def load_stock_data(self, ticker: str) -> Dict[str, Any]:
        ticker_path = self.data_path / f"{ticker}.VN"
        if not ticker_path.exists():
            ticker_path = self.data_path / ticker

        if not ticker_path.exists():
            return {"error": f"No data found for {ticker}"}

        data = {}
        for file in ["company_info.json", "financial_reports.json", "ohlc_prices.json"]:
            file_path = ticker_path / file
            if file_path.exists():
                with open(file_path) as f:
                    data[file.replace(".json", "")] = json.load(f)

        return data


# ── Technical helpers ────────────────────────────────────────
def _compute_sma(closes: List[float], window: int) -> float | None:
    if len(closes) < window:
        return None
    return sum(closes[-window:]) / window


def _compute_rsi(closes: List[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(len(closes) - period, len(closes))]
    gains = [d for d in deltas if d > 0]
    losses = [-d for d in deltas if d < 0]
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0.0001
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _compute_macd(closes: List[float]) -> Dict[str, float | None]:
    """MACD (12,26,9) line and signal."""
    def _ema(data: List[float], span: int) -> List[float]:
        k = 2 / (span + 1)
        ema_vals = [data[0]]
        for price in data[1:]:
            ema_vals.append(price * k + ema_vals[-1] * (1 - k))
        return ema_vals

    if len(closes) < 26:
        return {"macd": None, "signal": None, "histogram": None}
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = [a - b for a, b in zip(ema12, ema26)]
    signal_line = _ema(macd_line[-9:], 9) if len(macd_line) >= 9 else [0]
    histogram = macd_line[-1] - signal_line[-1]
    return {"macd": macd_line[-1], "signal": signal_line[-1], "histogram": histogram}


def _price_change_pct(prices: List[Dict], days: int) -> float | None:
    if len(prices) < days + 1:
        return None
    old = prices[-(days + 1)]["close"]
    new = prices[-1]["close"]
    if old == 0:
        return None
    return ((new - old) / old) * 100


# ── Analysis generators ─────────────────────────────────────
def _fundamental_analysis(ticker: str, timeframe: str, stock_data: Dict, round_num: int) -> str:
    """Generate data-driven fundamental analysis with price conditions."""
    info = stock_data.get("company_info", {}).get("info", {})
    fin = stock_data.get("financial_reports", {}).get("quarterly", {}).get("quarterly_financials", {})
    prices = stock_data.get("ohlc_prices", {}).get("prices", [])

    name = info.get("name", ticker)
    sector = info.get("sector", "N/A")
    market_cap = info.get("market_cap", 0)
    latest_price = prices[-1]["close"] if prices else 0

    # Extract most recent quarter metrics
    quarters = sorted(fin.keys(), reverse=True)
    latest = fin[quarters[0]] if quarters else {}
    prev = fin[quarters[1]] if len(quarters) > 1 else {}

    net_income = latest.get("Net Income", latest.get("Net Income Common Stockholders"))
    revenue = latest.get("Total Revenue", latest.get("Operating Revenue"))
    eps = latest.get("Basic EPS")
    prev_revenue = prev.get("Total Revenue", prev.get("Operating Revenue"))

    rev_growth = None
    if revenue and prev_revenue and prev_revenue != 0:
        rev_growth = ((revenue - prev_revenue) / abs(prev_revenue)) * 100

    # Compute fair value estimates for price conditions
    book_value = info.get("book_value", 0) or 0
    pe_ratio = info.get("pe_ratio") or (latest_price / eps if eps and eps > 0 else None)
    sector_pe = 12  # Vietnamese market average P/E proxy

    fair_value_pe = eps * sector_pe if eps and eps > 0 else None
    fair_value_pb = book_value * 1.5 if book_value > 0 else None  # 1.5x book value proxy

    # Use average of available fair values
    fair_values = [v for v in [fair_value_pe, fair_value_pb] if v and v > 0]
    target_price = sum(fair_values) / len(fair_values) if fair_values else latest_price * 1.1

    parts = [f"For {timeframe}: {name} ({sector}) has market cap {_fmt(market_cap)} VND."]
    if revenue:
        parts.append(f"Latest quarterly revenue: {_fmt(revenue)} VND.")
    if net_income:
        parts.append(f"Net income: {_fmt(net_income)} VND.")
    if eps:
        parts.append(f"EPS: {_fmt(eps, 0)} VND.")
    if rev_growth is not None:
        direction = "grew" if rev_growth > 0 else "declined"
        parts.append(f"Revenue {direction} {abs(rev_growth):.1f}% QoQ.")

    # Recommendation logic with price conditions
    if round_num == 1:
        if rev_growth is not None and rev_growth > 5 and net_income and net_income > 0:
            buy_price = latest_price * 0.98  # Entry below current by small margin
            parts.append(f"BUY below {_fmt(buy_price, 0)} VND for {timeframe} because strong revenue growth and profitability (fair value ~{_fmt(target_price, 0)} VND).")
        elif rev_growth is not None and rev_growth < -5:
            sell_price = latest_price * 1.02
            parts.append(f"SELL above {_fmt(sell_price, 0)} VND for {timeframe} because declining revenue trend.")
        else:
            hold_low = latest_price * 0.92
            hold_high = latest_price * 1.08
            parts.append(f"HOLD at {_fmt(hold_low, 0)}-{_fmt(hold_high, 0)} VND for {timeframe} because mixed fundamental signals.")
    else:
        # Round 2+ adds deeper analysis
        interest_income = latest.get("Interest Income")
        interest_expense = latest.get("Interest Expense")
        if interest_income and interest_expense:
            nim_proxy = interest_income - interest_expense
            parts.append(f"Net interest income: {_fmt(nim_proxy)} VND.")
        if len(quarters) >= 3:
            q3_rev = fin[quarters[2]].get("Total Revenue", fin[quarters[2]].get("Operating Revenue"))
            if q3_rev and revenue:
                yoy_approx = ((revenue - q3_rev) / abs(q3_rev)) * 100
                parts.append(f"~YoY revenue change: {yoy_approx:+.1f}%.")
        if rev_growth is not None and rev_growth > 0:
            buy_price = min(latest_price, target_price * 0.9)
            parts.append(f"BUY below {_fmt(buy_price, 0)} VND for {timeframe} because sustained growth trajectory (target {_fmt(target_price, 0)} VND).")
        else:
            hold_low = latest_price * 0.90
            hold_high = target_price
            parts.append(f"HOLD at {_fmt(hold_low, 0)}-{_fmt(hold_high, 0)} VND for {timeframe} because fundamentals need monitoring.")

    return " ".join(parts)


def _technical_analysis(ticker: str, timeframe: str, stock_data: Dict, round_num: int) -> str:
    """Generate data-driven technical analysis with price conditions."""
    prices = stock_data.get("ohlc_prices", {}).get("prices", [])
    if not prices:
        return f"For {timeframe}: Insufficient price data for {ticker}. HOLD due to lack of technical signals."

    closes = [p["close"] for p in prices]
    latest_price = closes[-1]
    sma20 = _compute_sma(closes, 20)
    sma50 = _compute_sma(closes, 50)
    sma200 = _compute_sma(closes, 200)
    rsi = _compute_rsi(closes)
    macd = _compute_macd(closes)

    chg_30d = _price_change_pct(prices, 30)
    chg_90d = _price_change_pct(prices, 90)

    high_52w = max(p["high"] for p in prices[-252:]) if len(prices) >= 252 else max(p["high"] for p in prices)
    low_52w = min(p["low"] for p in prices[-252:]) if len(prices) >= 252 else min(p["low"] for p in prices)

    # Compute support/resistance for price conditions
    support = sma50 if sma50 and sma50 < latest_price else (sma200 if sma200 and sma200 < latest_price else low_52w)
    resistance = high_52w if high_52w > latest_price else latest_price * 1.15

    parts = [f"For {timeframe}: {ticker} at {_fmt(latest_price, 0)} VND."]

    if round_num == 1:
        if sma20:
            pos = "above" if latest_price > sma20 else "below"
            parts.append(f"Price {pos} SMA20 ({_fmt(sma20, 0)}).")
        if sma50:
            pos = "above" if latest_price > sma50 else "below"
            parts.append(f"SMA50: {_fmt(sma50, 0)} ({pos}).")
        if rsi:
            zone = "overbought" if rsi > 70 else "oversold" if rsi < 30 else "neutral"
            parts.append(f"RSI(14): {rsi:.1f} ({zone}).")
        if chg_30d is not None:
            parts.append(f"30-day change: {chg_30d:+.1f}%.")

        # Technical recommendation with price conditions
        bullish_signals = 0
        if sma20 and latest_price > sma20:
            bullish_signals += 1
        if sma50 and latest_price > sma50:
            bullish_signals += 1
        if rsi and 30 < rsi < 70:
            bullish_signals += 1
        if chg_30d and chg_30d > 0:
            bullish_signals += 1

        if bullish_signals >= 3:
            buy_level = support * 1.01 if support else latest_price * 0.97
            parts.append(f"BUY below {_fmt(buy_level, 0)} VND for {timeframe} because multiple bullish signals aligned (support at {_fmt(support, 0)} VND).")
        elif bullish_signals <= 1:
            sell_level = latest_price * 1.03
            parts.append(f"SELL above {_fmt(sell_level, 0)} VND for {timeframe} because bearish technical setup (resistance at {_fmt(resistance, 0)} VND).")
        else:
            parts.append(f"HOLD at {_fmt(support, 0)}-{_fmt(resistance, 0)} VND for {timeframe} because mixed technical signals.")
    else:
        # Round 2+: MACD, support/resistance, volume
        if macd["macd"] is not None:
            cross = "bullish" if macd["histogram"] and macd["histogram"] > 0 else "bearish"
            parts.append(f"MACD: {macd['macd']:.1f}, signal: {macd['signal']:.1f} ({cross} crossover).")
        if sma200:
            pos = "above" if latest_price > sma200 else "below"
            parts.append(f"SMA200: {_fmt(sma200, 0)} ({pos} = {'bullish' if pos == 'above' else 'bearish'} long-term).")
        parts.append(f"52-week range: {_fmt(low_52w, 0)} - {_fmt(high_52w, 0)}.")
        if chg_90d is not None:
            parts.append(f"90-day change: {chg_90d:+.1f}%.")

        # Volume analysis
        recent_vols = [p["volume"] for p in prices[-20:]]
        avg_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 0
        last_vol = prices[-1]["volume"]
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1
        if vol_ratio > 1.5:
            parts.append(f"Volume spike: {vol_ratio:.1f}x average (high interest).")

        if macd["histogram"] and macd["histogram"] > 0 and sma200 and latest_price > sma200:
            buy_level = sma200 * 1.02
            parts.append(f"BUY below {_fmt(buy_level, 0)} VND for {timeframe} because MACD bullish and above SMA200 (support {_fmt(sma200, 0)} VND).")
        else:
            parts.append(f"HOLD at {_fmt(support, 0)}-{_fmt(resistance, 0)} VND for {timeframe} because technical picture needs confirmation.")

    return " ".join(parts)


def _sentiment_analysis(ticker: str, timeframe: str, stock_data: Dict, round_num: int) -> str:
    """Generate data-driven sentiment analysis with price conditions using price action as proxy."""
    prices = stock_data.get("ohlc_prices", {}).get("prices", [])
    info = stock_data.get("company_info", {}).get("info", {})
    sector = info.get("sector", "N/A")
    name = info.get("name", ticker)

    if not prices:
        return f"For {timeframe}: No price data for sentiment analysis of {ticker}. HOLD."

    closes = [p["close"] for p in prices]
    volumes = [p["volume"] for p in prices]
    latest_price = closes[-1]

    chg_7d = _price_change_pct(prices, 5)
    chg_30d = _price_change_pct(prices, 20)
    chg_90d = _price_change_pct(prices, 60)

    # Volatility as sentiment proxy
    if len(closes) >= 20:
        returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(-20, 0)]
        volatility = (sum(r**2 for r in returns) / len(returns)) ** 0.5 * 100
    else:
        volatility = None

    # Volume trend
    avg_vol_recent = sum(volumes[-10:]) / 10 if len(volumes) >= 10 else 0
    avg_vol_prior = sum(volumes[-30:-10]) / 20 if len(volumes) >= 30 else avg_vol_recent
    vol_trend = ((avg_vol_recent - avg_vol_prior) / avg_vol_prior * 100) if avg_vol_prior > 0 else 0

    # Sentiment-derived price levels
    sentiment_support = min(closes[-20:]) if len(closes) >= 20 else latest_price * 0.90
    sentiment_resistance = max(closes[-20:]) if len(closes) >= 20 else latest_price * 1.10

    parts = [f"For {timeframe}: {name} ({sector}) sentiment analysis."]

    if round_num == 1:
        if chg_7d is not None:
            mood = "positive" if chg_7d > 1 else "negative" if chg_7d < -1 else "neutral"
            parts.append(f"Short-term momentum {mood} ({chg_7d:+.1f}% weekly).")
        if chg_30d is not None:
            parts.append(f"Monthly sentiment: {chg_30d:+.1f}%.")
        if vol_trend:
            interest = "increasing" if vol_trend > 10 else "decreasing" if vol_trend < -10 else "stable"
            parts.append(f"Investor interest {interest} (volume {vol_trend:+.0f}%).")

        # Sentiment signal with price conditions
        sentiment_score = 0
        if chg_7d and chg_7d > 0:
            sentiment_score += 1
        if chg_30d and chg_30d > 0:
            sentiment_score += 1
        if vol_trend > 0:
            sentiment_score += 1

        if sentiment_score >= 2:
            buy_level = sentiment_support * 1.02
            parts.append(f"BUY below {_fmt(buy_level, 0)} VND for {timeframe} because positive momentum and growing investor interest (sentiment support {_fmt(sentiment_support, 0)} VND).")
        elif sentiment_score == 0:
            sell_level = latest_price * 1.02
            parts.append(f"SELL above {_fmt(sell_level, 0)} VND for {timeframe} because negative sentiment across indicators.")
        else:
            parts.append(f"HOLD at {_fmt(sentiment_support, 0)}-{_fmt(sentiment_resistance, 0)} VND for {timeframe} because mixed market sentiment.")
    else:
        if volatility is not None:
            risk_level = "high" if volatility > 3 else "moderate" if volatility > 1.5 else "low"
            parts.append(f"20-day volatility: {volatility:.2f}% ({risk_level} risk).")
        if chg_90d is not None:
            trend = "uptrend" if chg_90d > 10 else "downtrend" if chg_90d < -10 else "sideways"
            parts.append(f"3-month trend: {chg_90d:+.1f}% ({trend}).")

        # Consecutive up/down days
        streak = 0
        if len(closes) >= 2:
            direction = 1 if closes[-1] >= closes[-2] else -1
            for i in range(len(closes) - 1, 0, -1):
                if (closes[i] - closes[i - 1]) * direction >= 0:
                    streak += 1
                else:
                    break
            streak_type = "up" if direction > 0 else "down"
            parts.append(f"Current streak: {streak} consecutive {streak_type} days.")

        if chg_90d and chg_90d > 5 and volatility and volatility < 3:
            buy_level = sentiment_support * 1.01
            parts.append(f"BUY below {_fmt(buy_level, 0)} VND for {timeframe} because steady uptrend with manageable volatility (support {_fmt(sentiment_support, 0)} VND).")
        else:
            parts.append(f"HOLD at {_fmt(sentiment_support, 0)}-{_fmt(sentiment_resistance, 0)} VND for {timeframe} because sentiment requires more confirmation.")

    return " ".join(parts)


def _risk_manager_analysis(ticker: str, timeframe: str, stock_data: Dict, round_num: int) -> str:
    """Generate risk management analysis with stop-loss/take-profit levels."""
    prices = stock_data.get("ohlc_prices", {}).get("prices", [])
    info = stock_data.get("company_info", {}).get("info", {})
    name = info.get("name", ticker)

    if not prices:
        return f"For {timeframe}: Insufficient data for risk assessment of {ticker}. HOLD with caution."

    closes = [p["close"] for p in prices]
    volumes = [p["volume"] for p in prices]
    latest_price = closes[-1]

    # Compute volatility metrics
    if len(closes) >= 20:
        returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(-20, 0)]
        daily_vol = (sum(r**2 for r in returns) / len(returns)) ** 0.5
        annualized_vol = daily_vol * (252 ** 0.5) * 100
    else:
        daily_vol = 0.02
        annualized_vol = daily_vol * (252 ** 0.5) * 100

    # Max drawdown over available history
    peak = closes[0]
    max_dd = 0
    for price in closes:
        if price > peak:
            peak = price
        dd = (peak - price) / peak
        if dd > max_dd:
            max_dd = dd
    max_dd_pct = max_dd * 100

    # Average daily volume
    avg_vol = sum(volumes[-20:]) / min(len(volumes), 20) if volumes else 0

    # Risk-based price levels
    stop_loss = latest_price * (1 - 2 * daily_vol * 10)  # ~2 sigma over 10 days
    take_profit = latest_price * (1 + 3 * daily_vol * 10)  # ~3 sigma upside
    risk_reward = (take_profit - latest_price) / (latest_price - stop_loss) if latest_price > stop_loss else 0

    parts = [f"For {timeframe}: {name} risk assessment at {_fmt(latest_price, 0)} VND."]

    if round_num == 1:
        parts.append(f"Annualized volatility: {annualized_vol:.1f}%.")
        parts.append(f"Max drawdown (historical): {max_dd_pct:.1f}%.")
        parts.append(f"Avg daily volume: {_fmt(avg_vol, 0)} shares.")
        parts.append(
            f"Stop-loss at {_fmt(stop_loss, 0)} VND, "
            f"take-profit at {_fmt(take_profit, 0)} VND, "
            f"risk-reward ratio {risk_reward:.1f}:1."
        )
        if risk_reward >= 2:
            parts.append(f"HOLD with favorable risk-reward for {timeframe} (position size: max 5% of portfolio).")
        else:
            parts.append(f"HOLD with caution for {timeframe} — risk-reward {risk_reward:.1f}:1 is below 2:1 threshold.")
    else:
        # Round 2+: deeper risk metrics
        # Beta proxy: correlation with own trend
        sma50 = _compute_sma(closes, 50)
        trend_deviation = abs(latest_price - sma50) / sma50 * 100 if sma50 else 0
        parts.append(f"Price deviation from SMA50: {trend_deviation:.1f}%.")

        # Liquidity risk
        thin_vol_days = sum(1 for v in volumes[-20:] if v < avg_vol * 0.5) if volumes else 0
        if thin_vol_days > 5:
            parts.append(f"Liquidity concern: {thin_vol_days}/20 recent days below 50% avg volume.")

        # Tighter stops for round 2
        tight_stop = latest_price * (1 - 1.5 * daily_vol * 10)
        parts.append(
            f"Revised stop-loss at {_fmt(tight_stop, 0)} VND ({((latest_price - tight_stop) / latest_price * 100):.1f}% risk), "
            f"take-profit at {_fmt(take_profit, 0)} VND ({((take_profit - latest_price) / latest_price * 100):.1f}% upside)."
        )
        if risk_reward >= 1.5:
            parts.append(f"HOLD for {timeframe} — acceptable risk profile with disciplined stops.")
        else:
            parts.append(f"SELL above {_fmt(latest_price * 1.01, 0)} VND for {timeframe} — insufficient risk-reward.")

    return " ".join(parts)


def _judge_analysis(
    ticker: str,
    timeframe: str,
    round_num: int,
    max_rounds: int,
    responses: Dict[str, str],
    stock_data: Dict,
) -> str:
    """Generate judge decision with a strict confidence > 80% guardrail.

    Emits CONTINUE when confidence is ≤ 80%, NO_DECISION when max rounds
    are exhausted and confidence is still ≤ 80%, or CONCLUDE when the
    threshold is met.
    """
    buy_count = sum(1 for v in responses.values() if "BUY" in v.upper())
    sell_count = sum(1 for v in responses.values() if "SELL" in v.upper())
    hold_count = len(responses) - buy_count - sell_count
    num_analysts = len(responses)

    info = stock_data.get("company_info", {}).get("info", {})
    name = info.get("name", ticker)

    prices = stock_data.get("ohlc_prices", {}).get("prices", [])
    latest_price = prices[-1]["close"] if prices else 0

    # ── Compute numeric confidence from analyst consensus ─────
    max_consensus = max(buy_count, sell_count, hold_count)
    if max_consensus == num_analysts:
        confidence_pct = 93.0
    elif max_consensus == num_analysts - 1:      # 3 of 4
        confidence_pct = 83.0
    elif max_consensus == num_analysts - 2:      # 2 of 4
        confidence_pct = 58.0
    else:
        confidence_pct = 40.0

    # HOLD by default (no directional majority) caps out below threshold
    if buy_count < 2 and sell_count < 2:
        confidence_pct = min(confidence_pct, 58.0)

    # ── Round 1: always continue unless fully unanimous ───────
    if round_num < 2 and confidence_pct < 90.0:
        return (
            f"CONTINUE: Round {round_num} — confidence {confidence_pct:.0f}% is below 80% threshold. "
            f"{buy_count} BUY, {hold_count} HOLD, {sell_count} SELL. "
            f"Need deeper analysis with price conditions for {timeframe} on {name}."
        )

    # ── Confidence guardrail: force CONTINUE if threshold not met ──
    if not _confidence_meets_threshold(confidence_pct):
        if round_num < max_rounds:
            return (
                f"CONTINUE: Confidence {confidence_pct:.0f}% ≤ 80% threshold — "
                f"proceeding to Round {round_num + 1}/{max_rounds} for stronger consensus on {name} "
                f"({buy_count} BUY, {hold_count} HOLD, {sell_count} SELL)."
            )
        # Max rounds reached, threshold still not met → NO_DECISION
        return "\n".join([
            "NO_DECISION",
            "",
            f"**Confidence:** {confidence_pct:.0f}%",
            "**Reason:** CONFIDENCE_BELOW_THRESHOLD",
            f"**Analysis:** {buy_count}/{num_analysts} analysts BUY, "
            f"{sell_count}/{num_analysts} SELL, {hold_count}/{num_analysts} HOLD — "
            f"insufficient consensus reached for {name} after {max_rounds} rounds.",
            "**Recommendation:** Seek additional data, await earnings/catalyst, "
            "or reduce position size until clearer signals emerge.",
        ])

    # ── Confidence met (> 80%): build CONCLUDE verdict ────────
    if buy_count >= sell_count and buy_count >= hold_count:
        rec = "BUY"
        action_price = latest_price * 0.97
        price_condition = f"BUY below {_fmt(action_price, 0)} VND"
    elif sell_count > buy_count:
        rec = "SELL"
        action_price = latest_price * 1.02
        price_condition = f"SELL above {_fmt(action_price, 0)} VND"
    else:
        rec = "HOLD"
        hold_low = latest_price * 0.92
        hold_high = latest_price * 1.10
        price_condition = f"HOLD at {_fmt(hold_low, 0)}-{_fmt(hold_high, 0)} VND"

    target_price = (
        latest_price * 1.15 if rec == "BUY"
        else latest_price * 0.85 if rec == "SELL"
        else latest_price
    )
    stop_loss = (
        latest_price * 0.92 if rec == "BUY"
        else latest_price * 1.08 if rec == "SELL"
        else None
    )

    verdict_parts = [
        "CONCLUDE",
        "",
        f"**For {timeframe}: {price_condition}**",
        f"**Confidence:** {confidence_pct:.0f}%",
        f"**Price Target:** {_fmt(target_price, 0)} VND "
        f"({'upside' if rec == 'BUY' else 'downside' if rec == 'SELL' else 'fair value'})",
        "**Key Evidence:**",
        f"- Fundamental: {responses.get('fundamental', '')[:120]}",
        f"- Technical: {responses.get('technical', '')[:120]}",
        f"- Sentiment: {responses.get('sentiment', '')[:120]}",
        f"- Risk: {responses.get('risk_manager', '')[:120]}",
        "",
        f"**Reasoning:** {buy_count}/{num_analysts} analysts recommend BUY, "
        f"{sell_count}/{num_analysts} SELL, {hold_count}/{num_analysts} HOLD for {name} "
        f"at {_fmt(latest_price, 0)} VND. Consensus points to {rec} for {timeframe}.",
        "",
    ]
    if stop_loss:
        verdict_parts.append(
            f"**Risks:** Market volatility could impact {timeframe} outlook. "
            f"Stop-loss at {_fmt(stop_loss, 0)} VND."
        )
    else:
        verdict_parts.append(
            f"**Risks:** Market volatility and macroeconomic conditions could impact the {timeframe} outlook."
        )
    verdict_parts.append(
        f"**Monitor:** Quarterly earnings, sector rotation, and volume patterns. "
        f"Reassess if price breaks below {_fmt(latest_price * 0.90, 0)} VND "
        f"or above {_fmt(latest_price * 1.15, 0)} VND."
    )
    return "\n".join(verdict_parts)


class DebateEngine:
    """Local debate engine with data-driven analysis for development.
    
    Supports two modes:
    - auto: All agents (fundamental, technical, sentiment, risk_manager, judge) debate automatically
    - human: Agents debate but pause for human input between rounds
    """

    def __init__(self):
        self.data_loader = DataLoader()
        self.debate_history: List[str] = []

    def debate(
        self,
        ticker: str,
        timeframe: str,
        min_rounds: int,
        max_rounds: int,
        mode: str = DEBATE_MODE_AUTO,
        human_input: str | None = None,
    ) -> Dict[str, Any]:
        self.debate_history = []
        stock_data = self.data_loader.load_stock_data(ticker)
        if "error" in stock_data:
            raise ValueError(stock_data["error"])

        rounds_data = []
        current_round = 1
        should_continue = True

        while should_continue and current_round <= max_rounds:
            round_result = self._run_debate_round(
                ticker, timeframe, current_round, max_rounds, stock_data,
                human_input=human_input if current_round > 1 else None,
            )
            rounds_data.append(round_result)

            judge_decision = round_result.get("judge_decision", "")
            confidence_pct = _parse_confidence_percent(judge_decision)
            confidence_qualified = _confidence_meets_threshold(confidence_pct)

            # In human mode, break after each round to allow human interjection
            if mode == DEBATE_MODE_HUMAN and current_round >= 1 and not (
                "CONCLUDE" in judge_decision or "NO_DECISION" in judge_decision
            ):
                return {
                    "ticker": ticker,
                    "timeframe": timeframe,
                    "actual_rounds": current_round,
                    "rounds": rounds_data,
                    "mode": mode,
                    "status": "awaiting_human_input",
                    "final_recommendation": "",
                    "confidence": "",
                    "confidence_percent": confidence_pct,
                    "decision_qualified": False,
                    "rationale": "",
                    "risks": "",
                    "monitor": "",
                }

            # Continue when: judge asks CONTINUE, min_rounds not met, or threshold not yet met
            wants_continue = "CONTINUE" in judge_decision
            below_threshold = not confidence_qualified
            should_continue = (
                (wants_continue and current_round < max_rounds)
                or (current_round < min_rounds)
                or (below_threshold and current_round < max_rounds)
            )

            current_round += 1

        final_verdict = self._extract_final_verdict(rounds_data[-1]["judge_decision"])
        final_recommendation = final_verdict.get("recommendation", "NO_DECISION")
        final_confidence_pct = final_verdict.get("confidence_percent", 0.0)
        final_qualified = final_verdict.get("decision_qualified", False)

        return {
            "ticker": ticker,
            "timeframe": timeframe,
            "actual_rounds": current_round - 1,
            "rounds": rounds_data,
            "mode": mode,
            "status": "completed" if final_qualified else "no_decision",
            "final_recommendation": final_recommendation,
            "confidence": final_verdict.get("confidence", "Low"),
            "confidence_percent": final_confidence_pct,
            "decision_qualified": final_qualified,
            "rationale": final_verdict.get("reasoning", ""),
            "risks": final_verdict.get("risks", ""),
            "monitor": final_verdict.get("monitor", ""),
            "price_target": final_verdict.get("price_target", ""),
        }

    def _run_debate_round(
        self,
        ticker: str,
        timeframe: str,
        round_num: int,
        max_rounds: int,
        stock_data: Dict,
        human_input: str | None = None,
    ) -> Dict[str, str]:
        responses = {
            "fundamental": _fundamental_analysis(ticker, timeframe, stock_data, round_num),
            "technical": _technical_analysis(ticker, timeframe, stock_data, round_num),
            "sentiment": _sentiment_analysis(ticker, timeframe, stock_data, round_num),
            "risk_manager": _risk_manager_analysis(ticker, timeframe, stock_data, round_num),
        }

        for analyst, text in responses.items():
            self.debate_history.append(f"Round {round_num} {analyst.upper()}: {text[:200]}")

        if human_input:
            responses["human_input"] = human_input
            self.debate_history.append(f"Round {round_num} HUMAN: {human_input[:200]}")

        judge_result = _judge_analysis(ticker, timeframe, round_num, max_rounds, responses, stock_data)

        result = {
            "round_num": round_num,
            "fundamental": responses["fundamental"],
            "technical": responses["technical"],
            "sentiment": responses["sentiment"],
            "risk_manager": responses["risk_manager"],
            "judge_decision": judge_result,
        }
        if human_input:
            result["human_input"] = human_input
        return result

    def _extract_final_verdict(self, judge_output: str) -> Dict[str, str]:
        lines = judge_output.split("\n")
        confidence_pct = _parse_confidence_percent(judge_output)
        qualified = _confidence_meets_threshold(confidence_pct)

        verdict: Dict[str, Any] = {
            "recommendation": "HOLD",
            "confidence": "High" if confidence_pct > 80 else "Medium" if confidence_pct > 50 else "Low",
            "confidence_percent": confidence_pct,
            "decision_qualified": qualified,
            "reasoning": judge_output[:500],
            "risks": "",
            "monitor": "",
            "price_target": "",
        }

        # Handle NO_DECISION explicitly
        if judge_output.lstrip().startswith("NO_DECISION"):
            verdict["recommendation"] = "NO_DECISION"
            verdict["decision_qualified"] = False
            for line in lines:
                ll = line.lower()
                if "**reason:**" in ll:
                    verdict["reasoning"] = line.replace("**Reason:**", "").strip()
                elif "**recommendation:**" in ll:
                    verdict["monitor"] = line.replace("**Recommendation:**", "").strip()
            return verdict

        for line in lines:
            line_lower = line.lower()
            if line.startswith("**For") and ":" in line:
                if "buy" in line_lower:
                    verdict["recommendation"] = "BUY"
                elif "sell" in line_lower:
                    verdict["recommendation"] = "SELL"
            elif "buy" in line_lower and ("below" in line_lower or "for" in line_lower) and ":" not in line_lower:
                verdict["recommendation"] = "BUY"
            elif "sell" in line_lower and ("above" in line_lower or "for" in line_lower) and ":" not in line_lower:
                verdict["recommendation"] = "SELL"
            elif "**price target:**" in line_lower:
                verdict["price_target"] = line.replace("**Price Target:**", "").strip()
            elif "**reasoning:**" in line_lower:
                verdict["reasoning"] = line.replace("**Reasoning:**", "").strip()
            elif "**risks:**" in line_lower:
                verdict["risks"] = line.replace("**Risks:**", "").strip()
            elif "**monitor:**" in line_lower:
                verdict["monitor"] = line.replace("**Monitor:**", "").strip()

        return verdict
