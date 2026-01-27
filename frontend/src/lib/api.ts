import { SessionStatusResponse, SessionState, TickLog, ReliabilityStatus, AuditLogEntry } from '@/types/api';

const API_BASE = 'http://localhost:8000/api/v1';

export class ApiError extends Error {
    status: number;
    data: any;

    constructor(message: string, status: number, data?: any) {
        super(message);
        this.status = status;
        this.data = data;
    }
}

// =============================================================================
// Strategy Types
// =============================================================================

export interface StrategyListResponse {
    active_strategy: string;
    available_strategies: string[];
    count: number;
}

export interface ActiveStrategyResponse {
    name: string;
    content: string;
}

export interface SwitchStrategyResponse {
    success: boolean;
    message: string;
    new_strategy?: string;
}

export interface MarketFactsResponse {
    success: boolean;
    facts?: Record<string, any>;
    message?: string;
}

export interface KeyLevels {
    entry_zone?: number;
    stop_loss?: number;
    target?: number;
}

export interface LLMDecision {
    bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    action: 'TRADE' | 'WAIT' | 'MONITOR';
    confidence: number;
    reasoning: string;
    key_levels?: KeyLevels;
    structure_assessment?: string;
    session_assessment?: string;
    entry_conditions_met?: string[];
    blocking_factors?: string[];
}

// =============================================================================
// Strategy API
// =============================================================================

export async function getStrategies(): Promise<StrategyListResponse> {
    const res = await fetch(`${API_BASE}/strategies`);
    if (!res.ok) throw new ApiError('Failed to fetch strategies', res.status);
    return res.json();
}

export async function getActiveStrategy(): Promise<ActiveStrategyResponse> {
    const res = await fetch(`${API_BASE}/strategies/active`);
    if (!res.ok) throw new ApiError('Failed to fetch active strategy', res.status);
    return res.json();
}

export async function switchStrategy(strategyName: string): Promise<SwitchStrategyResponse> {
    const res = await fetch(`${API_BASE}/strategies/switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy_name: strategyName })
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new ApiError(err.detail || 'Failed to switch strategy', res.status);
    }
    return res.json();
}

// =============================================================================
// Debug API
// =============================================================================

export async function getMarketFacts(): Promise<MarketFactsResponse> {
    const res = await fetch(`${API_BASE}/debug/market-facts`);
    if (!res.ok) throw new ApiError('Failed to fetch market facts', res.status);
    return res.json();
}

export async function getReasoningSchema(): Promise<any> {
    const res = await fetch(`${API_BASE}/debug/reasoning-schema`);
    if (!res.ok) throw new ApiError('Failed to fetch reasoning schema', res.status);
    return res.json();
}

// =============================================================================
// Session API Client
// =============================================================================

export const apiClient = {
    async getSessionStatus(): Promise<SessionStatusResponse> {
        try {
            // 1. Fetch Session State
            const stateRes = await fetch(`${API_BASE}/session/state`);
            if (!stateRes.ok) {
                throw new ApiError('Failed to fetch session state', stateRes.status);
            }
            const state: SessionState = await stateRes.json();

            // 2. Fetch Tick/Audit Logs
            const logsRes = await fetch(`${API_BASE}/session/tick-history`);
            let logs: TickLog[] = [];
            if (logsRes.ok) {
                logs = await logsRes.json();
            }

            // 3. Fetch Audit Trail
            const auditRes = await fetch(`${API_BASE}/session/audit-trail`);
            let audit_log: AuditLogEntry[] = [];
            if (auditRes.ok) {
                audit_log = await auditRes.json();
            }

            // 4. Reliability Status
            const reliability: ReliabilityStatus = {
                pending_requests: 0,
                retry_count: 0
            };

            return {
                state,
                logs,
                audit_log,
                reliability
            };

        } catch (error: any) {
            if (error instanceof ApiError) throw error;
            throw new ApiError(error.message || 'Unknown network error', 0);
        }
    },

    async advanceTick(): Promise<any> {
        const res = await fetch(`${API_BASE}/session/advance`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ bars: 1 }),
        });

        if (res.status === 422) {
            const errData = await res.json();
            throw new ApiError(errData.message || 'Agent Execution Error', 422, errData);
        }

        if (res.status === 202) {
            return { status: 'WAITING' };
        }

        if (!res.ok) {
            throw new ApiError('Failed to advance tick', res.status);
        }

        return await res.json();
    },

    async resetSession(): Promise<any> {
        const res = await fetch(`${API_BASE}/session/reset`, {
            method: 'POST',
        });

        if (!res.ok) {
            throw new ApiError('Failed to reset session', res.status);
        }

        return await res.json();
    }
};

// =============================================================================
// Legacy/Dashboard API
// =============================================================================

export interface TradeSetupResponse {
    symbol: string;
    timestamp: string;
    text: string;
    confidence: number;
    status?: "TRADE_NOW" | "WAIT" | "NO_TRADE";
    reason_short?: string;
    setup: {
        confluence_score: number;
        name?: string;
        type?: string;
        entry_price?: number;
        stop_loss?: number;
        take_profit?: number[];
        rule_refs?: string[];
    };
    risk?: {
        rr?: number;
    };
    htf_bias: {
        value: "NEUTRAL" | "BULLISH" | "BEARISH";
        rule_refs: string[];
    };
    ltf_alignment: {
        alignment: "ALIGNED" | "NOT_ALIGNED";
        rule_refs: string[];
    };
    checklist: any;
    graph_nodes_triggered: string[];
    explanation: string;
    // New fields from Neuro-Symbolic Architecture
    llm_decision?: LLMDecision;
}

export interface DataConfig {
    htf_bars: number;
    ltf_bars: number;
    micro_bars: number;
}

export async function getHealth() {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('Health check failed');
    return res.json();
}

export async function getSession() {
    const res = await fetch(`${API_BASE}/session/current`);
    if (!res.ok) throw new Error('Failed to fetch session');
    return res.json();
}

export async function getDataConfig() {
    const res = await fetch(`${API_BASE}/data/config`);
    if (!res.ok) return { htf_bars: 50, ltf_bars: 100, micro_bars: 50 };
    return res.json();
}

export async function analyzeMarket(data: any): Promise<TradeSetupResponse> {
    const res = await fetch(`${API_BASE}/session/analyze`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ snapshot: data })
    });
    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Analysis failed');
    }
    const json = await res.json();
    return json.analysis;
}

// =============================================================================
// Chat API
// =============================================================================

export interface ChatResponse {
    message: string;
    suggestions: string[];
    timestamp: string;
}

export async function sendChatMessage(message: string): Promise<ChatResponse> {
    const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ message })
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Chat request failed');
    }
    return res.json();
}

// =============================================================================
// MT5 API
// =============================================================================

export interface MT5Status {
    available: boolean;
    connected: boolean;
    account_info?: any;
}

export interface MT5SymbolsResponse {
    symbols: string[];
}

export async function getMT5Status(): Promise<MT5Status> {
    const res = await fetch(`${API_BASE}/market-data/status`);
    if (!res.ok) return { available: false, connected: false };
    return res.json();
}

export async function getMT5Symbols(): Promise<MT5SymbolsResponse> {
    const res = await fetch(`${API_BASE}/market-data/symbols`);
    if (!res.ok) return { symbols: [] };
    return res.json();
}

export async function connectMT5(): Promise<{ success: boolean }> {
    const res = await fetch(`${API_BASE}/market-data/connect`, { method: 'POST' });
    if (!res.ok) return { success: false };
    return res.json();
}

// =============================================================================
// Session/Backtest API
// =============================================================================

export interface BacktestSessionState {
    mode: 'IDLE' | 'BACKTEST' | 'LIVE';
    symbol?: string;
    current_time?: string;
    current_bar_index?: number;
    total_bars?: number;
    starting_balance?: number;
    current_balance?: number;
}

export interface SessionStatistics {
    total_trades: number;
    winners: number;
    losers: number;
    win_rate: number;
    profit_factor: number;
    total_pnl_pips: number;
    total_pnl_usd: number;
    gross_profit_pips: number;
    gross_loss_pips: number;
    max_drawdown_pips: number;
    average_rr: number;
    largest_win_pips: number;
    largest_loss_pips: number;
    average_win_pips: number;
    average_loss_pips: number;
    consecutive_wins: number;
    consecutive_losses: number;
    current_balance: number;
    starting_balance: number;
}

export interface HierarchicalPosition {
    id: string;
    symbol: string;
    order_type: string;
    entry_price: number;
    current_price: number;
    stop_loss?: number;
    take_profit?: number;
    volume: number;
    pnl_pips: number;
    pnl_usd: number;
    open_time: string;
}

export interface HierarchicalClosedTrade {
    id: string;
    symbol: string;
    order_type: string;
    entry_price: number;
    exit_price: number;
    stop_loss?: number;
    take_profit?: number;
    volume: number;
    pnl_pips: number;
    pnl_usd: number;
    open_time: string;
    close_time: string;
    exit_reason: string;
}

export interface InitSessionRequest {
    symbol: string;
    mode: 'BACKTEST' | 'LIVE';
    start_time?: string;
    end_time?: string;
    starting_balance?: number;
    timeframes?: string[];
}

export interface AdvanceTimeRequest {
    bars: number;
    tick_mode?: boolean;
}

export interface AdvanceTimeResponse {
    success: boolean;
    current_bar_index: number;
    current_time: string;
    snapshot?: any;
}

export interface OrderRequest {
    symbol: string;
    order_type: 'MARKET_BUY' | 'MARKET_SELL' | 'LIMIT_BUY' | 'LIMIT_SELL';
    volume?: number;
    price?: number;
    stop_loss?: number;
    take_profit?: number;
}

export async function initSession(request: InitSessionRequest): Promise<{ success: boolean }> {
    const res = await fetch(`${API_BASE}/session/init`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
    });
    if (!res.ok) throw new ApiError('Failed to initialize session', res.status);
    return res.json();
}

export async function getBacktestSessionState(): Promise<BacktestSessionState | null> {
    const res = await fetch(`${API_BASE}/session/state`);
    if (!res.ok) return null;
    return res.json();
}

export async function advanceTime(request: AdvanceTimeRequest): Promise<AdvanceTimeResponse> {
    const res = await fetch(`${API_BASE}/session/advance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
    });
    if (!res.ok) throw new ApiError('Failed to advance time', res.status);
    return res.json();
}

export async function getSessionStatistics(): Promise<SessionStatistics> {
    const res = await fetch(`${API_BASE}/session/statistics`);
    if (!res.ok) throw new ApiError('Failed to fetch statistics', res.status);
    return res.json();
}

export async function analyzeCurrentBar(): Promise<{ success: boolean; analysis?: any; error?: string }> {
    const res = await fetch(`${API_BASE}/session/analyze`, { method: 'POST' });
    if (!res.ok) return { success: false, error: 'Analysis failed' };
    return res.json();
}

export async function downloadBacktestResults(): Promise<void> {
    const res = await fetch(`${API_BASE}/session/export`);
    if (!res.ok) throw new ApiError('Failed to export results', res.status);
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'backtest_results.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}

// =============================================================================
// History API
// =============================================================================

export interface DecisionRecord {
    id: string;
    timestamp: string;
    symbol: string;
    bias: string;
    action: string;
    confidence: number;
    reasoning: string;
    status?: 'TRADE_NOW' | 'WAIT' | 'NO_TRADE';
    reason?: string;
    action_taken?: 'APPROVED' | 'REJECTED' | 'PENDING';
}

export interface PerformanceMetrics {
    total_decisions: number;
    trade_count: number;
    total_trades: number;
    win_rate: number;
    avg_confidence: number;
    total_pnl: number;
    profit_factor: number;
}

export interface SimulatedTrade {
    id: string;
    symbol: string;
    entry_time: string;
    exit_time?: string;
    entry_price: number;
    exit_price?: number;
    direction: 'LONG' | 'SHORT';
    pnl_pips?: number;
    pnl?: number;
    status: 'OPEN' | 'CLOSED' | 'CLOSED_WIN' | 'CLOSED_LOSS';
}

export async function getDecisions(limit?: number): Promise<DecisionRecord[]> {
    const url = limit ? `${API_BASE}/history/decisions?limit=${limit}` : `${API_BASE}/history/decisions`;
    const res = await fetch(url);
    if (!res.ok) return [];
    return res.json();
}

export async function getPerformanceMetrics(): Promise<PerformanceMetrics> {
    const res = await fetch(`${API_BASE}/history/metrics`);
    if (!res.ok) return { total_decisions: 0, trade_count: 0, total_trades: 0, win_rate: 0, avg_confidence: 0, total_pnl: 0, profit_factor: 0 };
    return res.json();
}

export async function getSimulatedTrades(): Promise<SimulatedTrade[]> {
    const res = await fetch(`${API_BASE}/history/trades`);
    if (!res.ok) return [];
    return res.json();
}

// =============================================================================
// Settings API
// =============================================================================

export async function getMode(): Promise<{ mode: string }> {
    const res = await fetch(`${API_BASE}/settings/mode`);
    if (!res.ok) return { mode: 'ANALYSIS_ONLY' };
    return res.json();
}

export async function setMode(mode: string): Promise<{ success: boolean }> {
    const res = await fetch(`${API_BASE}/settings/mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode })
    });
    if (!res.ok) return { success: false };
    return res.json();
}

export async function updateDataConfig(config: DataConfig): Promise<{ success: boolean }> {
    const res = await fetch(`${API_BASE}/data/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    });
    if (!res.ok) return { success: false };
    return res.json();
}

export async function getDataModes(): Promise<{ modes: string[]; current: string }> {
    const res = await fetch(`${API_BASE}/data/modes`);
    if (!res.ok) return { modes: [], current: 'sample' };
    return res.json();
}
