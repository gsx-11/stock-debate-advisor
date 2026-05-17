/*
 * Frontend API Client for Stock Debate Advisor
 * TypeScript/JavaScript client for frontend integration
 */

// API Configuration - Use environment variable or default to AI-service on port 8000
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface DebateSession {
  session_id: string;
  symbol: string;
  rounds: number;
  status: string;
  created_at: string;
  data_loaded?: {
    financial_reports: number;
    technical_datapoints: number;
    news_articles: number;
  };
}

interface SessionInfo {
  session_id: string;
  symbol: string;
  created_at: string;
  current_round: number;
  data: {
    financial_reports: number;
    technical_datapoints: number;
    news_articles: number;
    current_price?: number;
  };
  verdict?: any;
  transcript_length: number;
}

interface KnowledgeData {
  session_id: string;
  type: string;
  knowledge: string;
}

export class DebateAdvisorClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  // Health & System
  async healthCheck(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/`);
    return response.json();
  }

  // Symbols
  async getAvailableSymbols(): Promise<string[]> {
    try {
      const response = await fetch(`${this.baseUrl}/companies`);
      if (!response.ok) {
        console.warn('Failed to fetch symbols from API, returning empty list');
        return [];
      }
      const data = await response.json();
      return data.symbols || [];
    } catch (error) {
      console.warn('Error fetching symbols:', error);
      return [];
    }
  }

  // Debate Sessions
  async startDebate(symbol: string, rounds: number = 3): Promise<DebateSession> {
    try {
      const response = await fetch(`${this.baseUrl}/debate/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: symbol, timeframe: '3 months', min_rounds: 1, max_rounds: rounds })
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to start debate' }));
        throw new Error(error.detail || 'Failed to start debate');
      }

      return response.json();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to start debate session';
      console.error('Start debate error:', message);
      throw new Error(message);
    }
  }

  async getSessionInfo(sessionId: string): Promise<SessionInfo> {
    try {
      const response = await fetch(`${this.baseUrl}/debate/status/${sessionId}`);
      if (!response.ok) throw new Error('Failed to get session info');
      return response.json();
    } catch (error) {
      console.warn('Get session info error:', error);
      throw error;
    }
  }

  async getSessionStatus(sessionId: string): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/debate/status/${sessionId}`);
      if (!response.ok) throw new Error('Failed to get session status');
      return response.json();
    } catch (error) {
      console.warn('Get session status error:', error);
      throw error;
    }
  }

  async runDebateRound(sessionId: string, roundNum: number): Promise<any> {
    try {
      const response = await fetch(
        `${this.baseUrl}/debate/${sessionId}/round/${roundNum}`,
        { method: 'POST' }
      );
      if (!response.ok) throw new Error('Failed to run debate round');
      return response.json();
    } catch (error) {
      console.warn('Run debate round error:', error);
      throw error;
    }
  }

  async getDebateResults(sessionId: string): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/debate/result/${sessionId}`);
      if (!response.ok) throw new Error('Failed to get results');
      return response.json();
    } catch (error) {
      console.warn('Get debate results error:', error);
      throw error;
    }
  }

  async endSession(sessionId: string): Promise<any> {
    try {
      const response = await fetch(
        `${this.baseUrl}/debate/${sessionId}`,
        { method: 'DELETE' }
      );
      if (!response.ok) throw new Error('Failed to end session');
      return response.json();
    } catch (error) {
      console.warn('End session error:', error);
      throw error;
    }
  }

  // Knowledge Management - with graceful fallback
  async getFundamentalKnowledge(sessionId: string): Promise<KnowledgeData> {
    try {
      const response = await fetch(
        `${this.baseUrl}/debate/${sessionId}/knowledge/fundamental`
      );
      if (!response.ok) throw new Error('Failed to get fundamental knowledge');
      return response.json();
    } catch (error) {
      console.warn('Get fundamental knowledge error:', error);
      return { session_id: sessionId, type: 'fundamental', knowledge: '' };
    }
  }

  async getTechnicalKnowledge(sessionId: string): Promise<KnowledgeData> {
    try {
      const response = await fetch(
        `${this.baseUrl}/debate/${sessionId}/knowledge/technical`
      );
      if (!response.ok) throw new Error('Failed to get technical knowledge');
      return response.json();
    } catch (error) {
      console.warn('Get technical knowledge error:', error);
      return { session_id: sessionId, type: 'technical', knowledge: '' };
    }
  }

  async getSentimentKnowledge(sessionId: string): Promise<KnowledgeData> {
    try {
      const response = await fetch(
        `${this.baseUrl}/debate/${sessionId}/knowledge/sentiment`
      );
      if (!response.ok) throw new Error('Failed to get sentiment knowledge');
      return response.json();
    } catch (error) {
      console.warn('Get sentiment knowledge error:', error);
      return { session_id: sessionId, type: 'sentiment', knowledge: '' };
    }
  }

  async getAllKnowledge(sessionId: string): Promise<any> {
    try {
      const response = await fetch(
        `${this.baseUrl}/debate/${sessionId}/knowledge/all`
      );
      if (!response.ok) throw new Error('Failed to get all knowledge');
      return response.json();
    } catch (error) {
      console.warn('Get all knowledge error:', error);
      return { knowledge: [] };
    }
  }

  // Data Access - with graceful fallback
  async getFinancialData(symbol: string): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/financials/${symbol}`);
      if (!response.ok) throw new Error('Failed to get financial data');
      return response.json();
    } catch (error) {
      console.warn('Get financial data error:', error);
      return { symbol, data: [] };
    }
  }

  async getTechnicalData(symbol: string): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/financials/${symbol}/metrics`);
      if (!response.ok) throw new Error('Failed to get technical data');
      return response.json();
    } catch (error) {
      console.warn('Get technical data error:', error);
      return { symbol, data: [] };
    }
  }

  async getNewsData(symbol: string): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/financials/${symbol}/news`);
      if (!response.ok) throw new Error('Failed to get news data');
      return response.json();
    } catch (error) {
      console.warn('Get news data error:', error);
      return { symbol, articles: [] };
    }
  }

  // Statistics
  async getStats(): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/stats`);
      if (!response.ok) throw new Error('Failed to get stats');
      return response.json();
    } catch (error) {
      console.warn('Get stats error:', error);
      return { total_sessions: 0, total_rounds: 0 };
    }
  }
}

// Export singleton instance
export const debateAdvisorClient = new DebateAdvisorClient();

// Type exports for frontend use
export type { DebateSession, SessionInfo, KnowledgeData };
