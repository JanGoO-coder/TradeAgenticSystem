const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// MT5 Connection Types
export interface MT5TerminalInfo {
    connected: boolean;
    trade_allowed: boolean;
    company: string;
    name: string;
    path: string;
}

export interface MT5Status {
    available: boolean;
    connected: boolean;
    terminal_info: MT5TerminalInfo | null;
}

export interface MT5SymbolsResponse {
    symbols: string[];
    count: number;
}

export interface MT5ConnectResponse {
    connected: boolean;
    message: string;
    terminal_info: MT5TerminalInfo | null;
}

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

// MT5 API Functions
export async function getMT5Status(): Promise<MT5Status> {
    const res = await fetch(`${API_BASE_URL}/api/v1/market-data/status`);
    if (!res.ok) throw new Error('Failed to fetch MT5 status');
    return res.json();
}

export async function connectMT5(): Promise<MT5ConnectResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/market-data/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error('Failed to connect to MT5');
    return res.json();
}

export async function disconnectMT5(): Promise<{ connected: boolean; message: string }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/market-data/disconnect`, {
        method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to disconnect from MT5');
    return res.json();
}

export async function getMT5Symbols(): Promise<MT5SymbolsResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/market-data/symbols`);
    if (!res.ok) throw new Error('Failed to fetch MT5 symbols');
    return res.json();
}

// MT5 Historical Data Types
export interface OHLCV {
    timestamp: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

export interface MT5HistoricalData {
    symbol: string;
    timestamp: string;
    timeframe_bars: Record<string, OHLCV[]>;
}

export interface MT5HistoricalRequest {
    symbol: string;
    timeframes?: string[];
    bar_counts?: Record<string, number>;
}

/**
 * Fetch historical market data from MT5.
 * Requires MT5 to be connected first.
 */
export async function fetchMT5HistoricalData(
    symbol: string,
    config?: DataConfig
): Promise<MT5HistoricalData> {
    // First ensure MT5 is connected
    const status = await getMT5Status();
    if (!status.connected) {
        // Auto-connect using credentials from backend
        await connectMT5();
    }

    const request: MT5HistoricalRequest = {
        symbol,
        timeframes: config?.timeframes || ["1H", "15M", "5M"],
        bar_counts: {
            "1H": config?.htf_bars || 50,
            "15M": config?.ltf_bars || 100,
            "5M": config?.micro_bars || 50,
        },
    };

    const res = await fetch(`${API_BASE_URL}/api/v1/market-data/historical`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
    });

    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: 'Failed to fetch MT5 data' }));
        throw new Error(error.detail || 'Failed to fetch MT5 historical data');
    }

    return res.json();
}

/**
 * Create market data payload for analysis from MT5 data.
 */
export async function createMT5MarketData(
    symbol: string,
    config?: DataConfig
): Promise<Record<string, unknown>> {
    const mt5Data = await fetchMT5HistoricalData(symbol, config);

    return {
        symbol,
        timestamp: mt5Data.timestamp,
        timeframe_bars: mt5Data.timeframe_bars,
        account_balance: 10000.0,
        risk_pct: 1.0,
        economic_calendar: []
    };
}

// ============================================================================
// Agent Analysis API (LLM-powered)
// ============================================================================

export interface AgentObservation {
    symbol: string;
    timestamp: string;
    current_price: number;
    summary: string;
    state_hash: string;
    htf_bias: Record<string, unknown>;
    ltf_alignment: Record<string, unknown>;
    session: Record<string, unknown>;
    killzone: Record<string, unknown>;
    sweeps: Array<Record<string, unknown>>;
    fvgs: Array<Record<string, unknown>>;
    premium_discount: Record<string, unknown>;
}

export interface AgentDecision {
    decision: 'TRADE' | 'WAIT' | 'NO_TRADE';
    confidence: number;
    reasoning: string | null;
    brief_reason: string;
    rule_citations: string[];
    setup: {
        direction: 'LONG' | 'SHORT';
        entry_zone: { low: number; high: number };
        stop_loss: number;
        take_profits: number[];
        invalidation: string;
    } | null;
    latency_ms: number;
    mode: string;
}

export interface AgentAnalysisResponse {
    observation: AgentObservation;
    decision: AgentDecision;
}

export interface StrategySearchResult {
    rule_ids: string[];
    source: string;
    headers: string;
    score: number;
}

export interface AIChat {
    message: string;
    sources: StrategySearchResult[];
    suggestions: string[];
    timestamp: string;
}

export interface RateLimitStatus {
    rpm_limit: number;
    burst_size: number;
    calls_last_minute: number;
    available_tokens: number;
}

// Agent Analysis Functions
export async function analyzeWithAgent(
    symbol: string,
    htfCandles: Record<string, unknown>[],
    ltfCandles: Record<string, unknown>[],
    mode: 'verbose' | 'concise' = 'verbose',
    microCandles?: Record<string, unknown>[]
): Promise<AgentAnalysisResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/agent/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            symbol,
            htf_candles: htfCandles,
            ltf_candles: ltfCandles,
            micro_candles: microCandles,
            mode
        }),
    });
    if (!res.ok) throw new Error('Failed to analyze with agent');
    return res.json();
}

export async function observeMarket(
    symbol: string,
    htfCandles: Record<string, unknown>[],
    ltfCandles: Record<string, unknown>[],
    microCandles?: Record<string, unknown>[]
): Promise<AgentObservation> {
    const res = await fetch(`${API_BASE_URL}/api/v1/agent/observe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            symbol,
            htf_candles: htfCandles,
            ltf_candles: ltfCandles,
            micro_candles: microCandles
        }),
    });
    if (!res.ok) throw new Error('Failed to observe market');
    return res.json();
}

export async function searchAgentStrategies(query: string, k = 5): Promise<{ query: string; results: StrategySearchResult[] }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/agent/strategies/search?query=${encodeURIComponent(query)}&k=${k}`);
    if (!res.ok) throw new Error('Failed to search strategies');
    return res.json();
}

export async function listStrategies(): Promise<{ rule_count: number; rules: string[]; collection: string }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/agent/strategies`);
    if (!res.ok) throw new Error('Failed to list strategies');
    return res.json();
}

export async function getAgentRule(ruleId: string): Promise<Record<string, unknown>> {
    const res = await fetch(`${API_BASE_URL}/api/v1/agent/strategies/rule/${encodeURIComponent(ruleId)}`);
    if (!res.ok) throw new Error('Failed to get rule');
    return res.json();
}

export async function reindexAgentStrategies(): Promise<{ message: string; rule_count: number }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/agent/strategies/reindex`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to reindex strategies');
    return res.json();
}

export async function getRateLimitStatus(): Promise<RateLimitStatus> {
    const res = await fetch(`${API_BASE_URL}/api/v1/agent/rate-limit/status`);
    if (!res.ok) throw new Error('Failed to get rate limit status');
    return res.json();
}

export async function sendAIChat(
    message: string,
    context?: Record<string, unknown>,
    history?: Array<{ role: string; content: string }>
): Promise<AIChat> {
    const res = await fetch(`${API_BASE_URL}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, context, history }),
    });
    if (!res.ok) throw new Error('Failed to send AI chat');
    return res.json();
}

// ============================================================================
// Smart Backtest API
// ============================================================================

export interface BacktestMT5Status {
    connected: boolean;
    available: boolean;
}

export interface BacktestSession {
    session_id: string;
    symbol: string;
    from_date: string;
    to_date: string;
    status: 'created' | 'running' | 'paused' | 'completed' | 'error';
    progress: number;
    current_index: number;
    total_candles: number;
    data_source: 'mt5';  // Only MT5 supported - no sample data fallback
}

export interface BacktestTrade {
    id: string;
    direction: 'LONG' | 'SHORT';
    entry_price: number;
    entry_time: string;
    stop_loss: number;
    take_profits: number[];
    status: 'open' | 'won' | 'lost' | 'breakeven';
    exit_price?: number;
    exit_time?: string;
    pnl_r?: number;
    rule_citations: string[];
}

export interface BacktestPerformance {
    total_trades: number;
    wins: number;
    losses: number;
    breakeven: number;
    win_rate: number;
    total_pnl_r: number;
    max_drawdown_r: number;
    expectancy_r: number;
    equity_curve: Array<{ timestamp: string; equity: number }>;
}

export interface BacktestResults {
    session_id: string;
    status: string;
    progress: number;
    decisions_count: number;
    trades_count: number;
    performance: BacktestPerformance;
    trades: BacktestTrade[];
}

// Backtest Functions
export async function getBacktestMT5Status(): Promise<BacktestMT5Status> {
    const res = await fetch(`${API_BASE_URL}/api/v1/backtest/mt5-status`);
    if (!res.ok) throw new Error('Failed to get MT5 status');
    return res.json();
}

export async function createBacktestSession(
    symbol: string,
    fromDate: Date,
    toDate: Date,
    htfTimeframe = '1H',
    ltfTimeframe = '15M'
): Promise<BacktestSession> {
    const res = await fetch(`${API_BASE_URL}/api/v1/backtest/session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            symbol,
            from_date: fromDate.toISOString(),
            to_date: toDate.toISOString(),
            htf_timeframe: htfTimeframe,
            ltf_timeframe: ltfTimeframe
        }),
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: 'Unknown error' }));
        const errorMessage = errorData.detail || 'Failed to create backtest session';
        throw new Error(errorMessage);
    }
    return res.json();
}

export async function getBacktestSession(): Promise<BacktestSession> {
    const res = await fetch(`${API_BASE_URL}/api/v1/backtest/session`);
    if (!res.ok) throw new Error('Failed to get backtest session');
    return res.json();
}

export async function listBacktestSessions(): Promise<{ count: number; sessions: BacktestSession[] }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/backtest/sessions`);
    if (!res.ok) throw new Error('Failed to list backtest sessions');
    return res.json();
}

export async function stepForward(bars = 1): Promise<Record<string, unknown>> {
    const res = await fetch(`${API_BASE_URL}/api/v1/backtest/step/forward`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bars }),
    });
    if (!res.ok) throw new Error('Failed to step forward');
    return res.json();
}

export async function stepBackward(bars = 1): Promise<Record<string, unknown>> {
    const res = await fetch(`${API_BASE_URL}/api/v1/backtest/step/backward`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bars }),
    });
    if (!res.ok) throw new Error('Failed to step backward');
    return res.json();
}

export async function jumpToIndex(index: number): Promise<Record<string, unknown>> {
    const res = await fetch(`${API_BASE_URL}/api/v1/backtest/jump`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index }),
    });
    if (!res.ok) throw new Error('Failed to jump to index');
    return res.json();
}

export async function getBacktestSnapshot(): Promise<Record<string, unknown>> {
    const res = await fetch(`${API_BASE_URL}/api/v1/backtest/snapshot`);
    if (!res.ok) throw new Error('Failed to get backtest snapshot');
    return res.json();
}

export async function analyzeAtPosition(mode: 'verbose' | 'concise' = 'verbose'): Promise<Record<string, unknown>> {
    const res = await fetch(`${API_BASE_URL}/api/v1/backtest/analyze?mode=${mode}`, {
        method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to analyze at position');
    return res.json();
}

export async function getBacktestResults(): Promise<BacktestResults> {
    const res = await fetch(`${API_BASE_URL}/api/v1/backtest/results`);
    if (!res.ok) throw new Error('Failed to get backtest results');
    return res.json();
}

export async function getEquityCurve(): Promise<{ curve: Array<{ timestamp: string; equity: number }>; max_drawdown_r: number; total_pnl_r: number }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/backtest/equity-curve`);
    if (!res.ok) throw new Error('Failed to get equity curve');
    return res.json();
}

// Run batch backtest with SSE progress streaming
export function runBatchBacktest(
    stepSize = 1,
    maxConcurrent = 10,
    onProgress: (event: Record<string, unknown>) => void,
    onComplete: () => void,
    onError: (error: Error) => void
): () => void {
    const eventSource = new EventSource(
        `${API_BASE_URL}/api/v1/backtest/run?step_size=${stepSize}&max_concurrent=${maxConcurrent}`
    );

    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'completed') {
                onComplete();
                eventSource.close();
            } else {
                onProgress(data);
            }
        } catch (e) {
            console.error('Failed to parse backtest event', e);
        }
    };

    eventSource.onerror = () => {
        onError(new Error('Backtest stream error'));
        eventSource.close();
    };

    // Return cleanup function
    return () => eventSource.close();
}

// ============================================================================
// Services Health Check
// ============================================================================

export interface ServicesHealth {
    status: 'healthy' | 'degraded';
    timestamp: string;
    services: {
        chromadb: { status: string; connected?: boolean; error?: string };
        gemini: { status: string; rpm_limit?: number; calls_last_minute?: number; error?: string };
        strategy_store: { status: string; rules_loaded?: number; error?: string };
    };
}

export async function getServicesHealth(): Promise<ServicesHealth> {
    const res = await fetch(`${API_BASE_URL}/api/v1/health/services`);
    if (!res.ok) throw new Error('Failed to get services health');
    return res.json();
}

// ============================================================================
// Strategy Management
// ============================================================================

export interface StrategyFile {
    filename: string;
    path: string;
    size_bytes: number;
    modified_at: string;
    rule_count: number;
}

export interface StrategySearchResult {
    content: string;
    source: string;
    headers: string;
    rule_ids: string[];
    score: number;
}

export async function listStrategyFiles(): Promise<{ files: StrategyFile[]; total: number; directory: string }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/strategies/files`);
    if (!res.ok) throw new Error('Failed to list strategy files');
    return res.json();
}

export async function getStrategyFile(filename: string): Promise<{ filename: string; content: string; size_bytes: number }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/strategies/file/${encodeURIComponent(filename)}`);
    if (!res.ok) throw new Error('Failed to get strategy file');
    return res.json();
}

export async function addStrategy(name: string, content: string, description?: string): Promise<{ message: string; path: string; indexed: boolean }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/strategies/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, content, description }),
    });
    if (!res.ok) throw new Error('Failed to add strategy');
    return res.json();
}

export async function updateStrategyFile(filename: string, content: string): Promise<{ message: string; backup_created: string; indexed: boolean }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/strategies/file/${encodeURIComponent(filename)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(content),
    });
    if (!res.ok) throw new Error('Failed to update strategy file');
    return res.json();
}

export async function deleteStrategyFile(filename: string, createBackup = true): Promise<{ message: string; backup_path: string | null; indexed: boolean }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/strategies/file/${encodeURIComponent(filename)}?create_backup=${createBackup}`, {
        method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete strategy file');
    return res.json();
}

export async function searchStrategies(query: string, limit = 5, ruleFilter?: string): Promise<{ query: string; results: StrategySearchResult[]; count: number }> {
    let url = `${API_BASE_URL}/api/v1/strategies/search?query=${encodeURIComponent(query)}&limit=${limit}`;
    if (ruleFilter) url += `&rule_filter=${encodeURIComponent(ruleFilter)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to search strategies');
    return res.json();
}

export async function getRule(ruleId: string): Promise<{ rule_id: string; content: string; source: string; headers: string; rule_ids: string[] }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/strategies/rule/${encodeURIComponent(ruleId)}`);
    if (!res.ok) throw new Error('Failed to get rule');
    return res.json();
}

export async function listAllRules(): Promise<{ rules: string[]; count: number }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/strategies/rules`);
    if (!res.ok) throw new Error('Failed to list rules');
    return res.json();
}

export async function reindexStrategies(): Promise<{ message: string; rules_indexed: number; timestamp: string }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/strategies/reindex`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to reindex strategies');
    return res.json();
}

export async function getIndexStatus(): Promise<{ vector_store: { healthy: boolean }; collection: string; chunks_indexed: number; strategy_files: number; strategies_dir: string }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/strategies/index/status`);
    if (!res.ok) throw new Error('Failed to get index status');
    return res.json();
}
