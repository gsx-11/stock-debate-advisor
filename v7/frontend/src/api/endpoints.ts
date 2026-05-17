import { atom } from 'jotai';
import { apiClient } from './client';

// ============================================================================
// Types — aligned with AI-service v3.0 DebateResponse
// ============================================================================

export interface DebateRequest {
  symbol: string;
  context?: string;
  mode?: 'auto' | 'human';
}

export interface DebateRound {
  round_num: number;
  fundamental: string;
  technical: string;
  sentiment: string;
  risk_manager: string;
  judge_decision: string;
  human_input?: string | null;
}

export interface DebateResponse {
  session_id: string;
  ticker: string;
  symbol: string;
  timeframe: string;
  actual_rounds: number;
  rounds: DebateRound[];
  mode: string;
  status: string;
  final_recommendation: string;
  confidence: string;
  rationale: string;
  risks: string;
  monitor: string;
  price_target: string;
  // Numeric confidence and qualification flag from backend guardrail
  confidence_percent?: number;
  decision_qualified?: boolean;
  // Derived fields for UI convenience
  agents: AgentResponse[];
  moderator_summary: string;
  judge_decision: JudgeDecision;
  confidence_score: number;
  timestamp: string;
}

export interface AgentResponse {
  agent_name: string;
  agent_type: 'fundamental' | 'technical' | 'sentiment' | 'risk_manager';
  analysis: string;
  confidence: number;
  key_points: string[];
}

export interface JudgeDecision {
  recommendation: 'buy' | 'hold' | 'sell';
  rationale: string;
  confidence_score: number;
  key_factors: string[];
}

export interface CompanyData {
  symbol: string;
  company: Record<string, unknown>;
  financial: Record<string, unknown>;
  prices: Record<string, unknown>;
}

export interface CompanyInfo {
  symbol: string;
  name?: string;
  description?: string;
  sector?: string;
  industry?: string;
  website?: string;
  employees?: number;
  founded?: string;
  headquarters?: string;
  ceo?: string;
  [key: string]: unknown;
}

export interface NewsItem {
  id?: string;
  title?: string;
  content?: string;
  source?: string;
  published_at?: string;
  sentiment?: 'positive' | 'neutral' | 'negative';
  relevance_score?: number;
  [key: string]: unknown;
}

export interface MarketAnalysis {
  timestamp?: string;
  market_indices?: unknown[];
  sector_performance?: unknown[];
  volatility_index?: number;
  market_sentiment?: string;
  macroeconomic_indicators?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface LoadingState {
  isLoading: boolean;
  error: string | null;
}

// ============================================================================
// Atoms for Loading States
// ============================================================================

export const debateLoadingAtom = atom<LoadingState>({
  isLoading: false,
  error: null,
});

export const companyLoadingAtom = atom<LoadingState>({
  isLoading: false,
  error: null,
});

export const financialLoadingAtom = atom<LoadingState>({
  isLoading: false,
  error: null,
});

export const newsLoadingAtom = atom<LoadingState>({
  isLoading: false,
  error: null,
});

export const marketLoadingAtom = atom<LoadingState>({
  isLoading: false,
  error: null,
});

// ============================================================================
// Atoms for Data
// ============================================================================

export const debateResultAtom = atom<DebateResponse | null>(null);
export const companyDataAtom = atom<CompanyData | null>(null);
export const financialDataAtom = atom<Record<string, unknown> | null>(null);
export const companyInfoAtom = atom<CompanyInfo | null>(null);
export const newsAtom = atom<NewsItem[] | null>(null);
export const marketAnalysisAtom = atom<MarketAnalysis | null>(null);

// ============================================================================
// Helpers
// ============================================================================

function parseConfidence(raw: string | number): number {
  if (typeof raw === 'number') return raw;
  const match = String(raw).match(/[\d.]+/);
  return match ? parseFloat(match[0]) / 100 : 0.5;
}

function mapRecommendation(raw: string): 'buy' | 'hold' | 'sell' {
  const upper = String(raw).toUpperCase();
  if (upper.includes('BUY')) return 'buy';
  if (upper.includes('SELL')) return 'sell';
  return 'hold';
}

function extractAgents(rounds: DebateRound[]): AgentResponse[] {
  if (!rounds || rounds.length === 0) return [];
  const lastRound = rounds[rounds.length - 1];
  const agentTypes = ['fundamental', 'technical', 'sentiment', 'risk_manager'] as const;
  return agentTypes
    .filter((t) => lastRound[t])
    .map((t) => ({
      agent_name: t.charAt(0).toUpperCase() + t.slice(1).replace('_', ' '),
      agent_type: t,
      analysis: lastRound[t],
      confidence: 0.8,
      key_points: [],
    }));
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Run multi-agent debate on a stock
 * 1. POST /debate/start  → returns DebateResponse with session_id
 * 2. GET  /debate/status/{id} → poll (optional, result already in step 1 for sync engine)
 * 3. GET  /debate/result/{id} → get full result
 */
export const fetchDebateAsync = async (
  params: DebateRequest
): Promise<DebateResponse> => {
  try {
    const raw = await apiClient.post<Record<string, unknown>>(
      '/debate/start',
      {
        ticker: params.symbol,
        timeframe: '3 months',
        min_rounds: 1,
        max_rounds: 3,
        mode: params.mode || 'auto',
      }
    );

    const rounds = (raw.rounds || []) as DebateRound[];
    const confidenceNum = parseConfidence(raw.confidence as string);
    const rec = mapRecommendation(raw.final_recommendation as string);

    return {
      session_id: (raw.session_id || '') as string,
      ticker: (raw.ticker || params.symbol) as string,
      symbol: params.symbol,
      timeframe: (raw.timeframe || '3 months') as string,
      actual_rounds: (raw.actual_rounds || 0) as number,
      rounds,
      mode: (raw.mode || 'auto') as string,
      status: (raw.status || 'completed') as string,
      final_recommendation: (raw.final_recommendation || 'HOLD') as string,
      confidence: (raw.confidence || '50%') as string,
      rationale: (raw.rationale || '') as string,
      risks: (raw.risks || '') as string,
      monitor: (raw.monitor || '') as string,
      price_target: (raw.price_target || '') as string,
      agents: extractAgents(rounds),
      moderator_summary: (raw.rationale || 'Debate completed') as string,
      judge_decision: {
        recommendation: rec,
        rationale: (raw.rationale || '') as string,
        confidence_score: confidenceNum,
        key_factors: [],
      },
      confidence_score: confidenceNum,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    throw new Error('Failed to run debate. Please try again.');
  }
};

/**
 * Fetch available stock symbols
 */
export const fetchCompaniesAsync = async (): Promise<string[]> => {
  try {
    const data = await apiClient.get<{ symbols: string[]; count: number }>('/companies');
    return data.symbols;
  } catch {
    return [];
  }
};

/**
 * Fetch company data (info + financial + prices)
 */
export const fetchCompanyDataAsync = async (
  symbol: string
): Promise<CompanyData> => {
  try {
    return await apiClient.get<CompanyData>(`/company/${symbol}`);
  } catch {
    return { symbol, company: {}, financial: {}, prices: {} };
  }
};

/**
 * Fetch financial data for a stock symbol
 */
export const fetchFinancialDataAsync = async (
  symbol: string
): Promise<Record<string, unknown>> => {
  try {
    return await apiClient.get<Record<string, unknown>>(`/financials/${symbol}`);
  } catch {
    return { symbol };
  }
};

/**
 * Fetch company info for a stock symbol
 */
export const fetchCompanyInfoAsync = async (symbol: string): Promise<CompanyInfo> => {
  try {
    return await apiClient.get<CompanyInfo>(`/company/${symbol}`);
  } catch {
    return { symbol };
  }
};

/**
 * Fetch related news for a stock symbol
 */
export const fetchNewsAsync = async (
  symbol: string,
  limit = 10
): Promise<NewsItem[]> => {
  try {
    return await apiClient.get<NewsItem[]>(`/financials/${symbol}/news`, {
      params: { limit },
    });
  } catch {
    return [];
  }
};

/**
 * Fetch global market analysis overview
 */
export const fetchMarketAnalysisAsync = async (): Promise<MarketAnalysis> => {
  try {
    return await apiClient.get<MarketAnalysis>('/market-analysis');
  } catch {
    return {
      timestamp: new Date().toISOString(),
      confidence_percent: (raw.confidence_percent ?? 0) as number,
      decision_qualified: (raw.decision_qualified ?? false) as boolean,
      market_indices: [],
      sector_performance: [],
      market_sentiment: 'neutral',
      macroeconomic_indicators: {},
    };
  }
};

/**
 * Fetch core analysis datasets concurrently
 */
export const fetchComprehensiveAnalysisAsync = async (
  symbol: string
): Promise<{
  financial: Record<string, unknown>;
  company: CompanyInfo;
  news: NewsItem[];
}> => {
  const [financial, company, news] = await Promise.all([
    fetchFinancialDataAsync(symbol),
    fetchCompanyInfoAsync(symbol),
    fetchNewsAsync(symbol),
  ]);

  return { financial, company, news };
};
