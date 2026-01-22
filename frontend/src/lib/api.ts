const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface SessionInfo {
    session: string;
    kill_zone_active: boolean;
    kill_zone_name: string | null;
    time_until_next_zone: number | null;
    current_time_utc: string;
    current_time_est: string;
}

export interface KillZoneStatus {
    in_kill_zone: boolean;
    session: string | null;
    rule_refs: string[];
}

export interface HealthStatus {
    status: string;
    agent_available: boolean;
    mode: string;
    timestamp: string;
}

export interface DataConfig {
    htf_bars: number;
    ltf_bars: number;
    micro_bars: number;
    timeframes: string[];
    live_refresh_interval: number;
    data_mode: string;
}

export interface DataMode {
    value: string;
    label: string;
    description: string;
}

export interface HTFBias {
    value: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    rule_refs: string[];
}

export interface LTFAlignment {
    timeframe: string;
    alignment: 'ALIGNED' | 'NOT_ALIGNED';
    rule_refs: string[];
}

export interface TradeSetup {
    name: string;
    type: string;
    entry_price: number | null;
    entry_type: string | null;
    stop_loss: number | null;
    take_profit: number[] | null;
    invalidation_point: number | null;
    is_counter_trend: boolean;
    confluence_score: number;
    rule_refs: string[];
}

export interface RiskParams {
    account_balance: number;
    risk_pct: number;
    position_size: number;
    rr: number | null;
}

export interface Checklist {
    htf_bias_exists: boolean;
    ltf_mss: boolean;
    pd_alignment: boolean;
    liquidity_sweep_detected: boolean;
    session_ok: boolean;
    news_ok: boolean;
    rr_minimum_met: boolean;
}

export interface TradeSetupResponse {
    symbol: string;
    timestamp: string;
    status: 'TRADE_NOW' | 'WAIT' | 'NO_TRADE';
    reason_short: string;
    htf_bias: HTFBias;
    ltf_alignment: LTFAlignment;
    setup: TradeSetup;
    risk: RiskParams;
    checklist: Checklist;
    explanation: string;
    graph_nodes_triggered: string[];
    confidence: number;
}

export interface ChatResponse {
    message: string;
    suggestions: string[];
    timestamp: string;
}

export interface ModeResponse {
    mode: 'ANALYSIS_ONLY' | 'SIMULATION' | 'APPROVAL_REQUIRED' | 'EXECUTION';
    description: string;
    can_execute: boolean;
}

export interface SimulatedTrade {
    id: string;
    symbol: string;
    direction: string;
    entry_price: number;
    stop_loss: number;
    take_profit: number;
    position_size: number;
    status: string;
    entry_time: string;
    exit_time: string | null;
    exit_price: number | null;
    pnl: number | null;
    setup_name: string;
    confluence_score: number;
}

export interface DecisionRecord {
    id: string;
    timestamp: string;
    symbol: string;
    status: string;
    reason: string;
    setup_name: string | null;
    action_taken: string;
    outcome: string | null;
}

export interface PerformanceMetrics {
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    win_rate: number;
    total_pnl: number;
    largest_win: number;
    largest_loss: number;
    average_rr: number;
    profit_factor: number;
}

// API Functions
export async function getHealth(): Promise<HealthStatus> {
    const res = await fetch(`${API_BASE_URL}/api/v1/health`);
    if (!res.ok) throw new Error('Failed to fetch health');
    return res.json();
}

export async function getSession(): Promise<SessionInfo> {
    const res = await fetch(`${API_BASE_URL}/api/v1/session/current`);
    if (!res.ok) throw new Error('Failed to fetch session');
    return res.json();
}

export async function getKillZoneStatus(): Promise<KillZoneStatus> {
    const res = await fetch(`${API_BASE_URL}/api/v1/killzone/status`);
    if (!res.ok) throw new Error('Failed to fetch kill zone status');
    return res.json();
}

export async function analyzeMarket(snapshot: Record<string, unknown>): Promise<TradeSetupResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(snapshot),
    });
    if (!res.ok) throw new Error('Failed to analyze market');
    return res.json();
}

export async function sendChatMessage(message: string): Promise<ChatResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
    });
    if (!res.ok) throw new Error('Failed to send chat message');
    return res.json();
}

// Execution Mode API
export async function getMode(): Promise<ModeResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/mode`);
    if (!res.ok) throw new Error('Failed to fetch mode');
    return res.json();
}

export async function setMode(mode: string): Promise<ModeResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/mode`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
    });
    if (!res.ok) throw new Error('Failed to set mode');
    return res.json();
}

// Simulation API
export async function getSimulatedTrades(): Promise<SimulatedTrade[]> {
    const res = await fetch(`${API_BASE_URL}/api/v1/trades/simulated`);
    if (!res.ok) throw new Error('Failed to fetch trades');
    return res.json();
}

export async function simulateTrade(trade: Omit<SimulatedTrade, 'id' | 'status' | 'entry_time' | 'exit_time' | 'exit_price' | 'pnl'>): Promise<SimulatedTrade> {
    const res = await fetch(`${API_BASE_URL}/api/v1/execute/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(trade),
    });
    if (!res.ok) throw new Error('Failed to simulate trade');
    return res.json();
}

// Audit API
export async function getDecisions(limit = 50): Promise<DecisionRecord[]> {
    const res = await fetch(`${API_BASE_URL}/api/v1/audit/decisions?limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch decisions');
    return res.json();
}

export async function getPerformanceMetrics(): Promise<PerformanceMetrics> {
    const res = await fetch(`${API_BASE_URL}/api/v1/audit/metrics`);
    if (!res.ok) throw new Error('Failed to fetch metrics');
    return res.json();
}

// WebSocket connection helper
export function createWebSocketConnection(): WebSocket | null {
    const wsUrl = API_BASE_URL.replace('http', 'ws') + '/ws/stream';
    try {
        return new WebSocket(wsUrl);
    } catch {
        console.error('Failed to create WebSocket connection');
        return null;
    }
}

// Data Configuration API
export async function getDataConfig(): Promise<DataConfig> {
    const res = await fetch(`${API_BASE_URL}/api/v1/data/config`);
    if (!res.ok) throw new Error('Failed to fetch data config');
    return res.json();
}

export async function updateDataConfig(config: DataConfig): Promise<DataConfig> {
    const res = await fetch(`${API_BASE_URL}/api/v1/data/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
    });
    if (!res.ok) throw new Error('Failed to update data config');
    return res.json();
}

export async function getDataModes(): Promise<{ modes: DataMode[] }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/data/modes`);
    if (!res.ok) throw new Error('Failed to fetch data modes');
    return res.json();
}
