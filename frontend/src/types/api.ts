export enum AgentPhase {
    IDLE = "IDLE",
    ANALYZING = "ANALYZING",
    DECIDING = "DECIDING",
    EXECUTING = "EXECUTING",
    WAITING = "WAITING",
    BOOTING = "BOOTING"
}

export interface ReliabilityStatus {
    pending_requests: number;
    retry_count: number;
}

export interface TickLog {
    tick: number;
    time: string;
    events: Array<{
        agent: string;
        action: string;
    }>;
}

export interface AuditLogEntry {
    id: string;
    timestamp: string;
    from_agent: string;
    to_agent: string;
    action: string;
    payload: any;
    correlation_id: string;
}

export interface SessionState {
    session_id: string | null;
    symbol: string | null;
    mode: string | null;
    current_time: string | null;
    simulation_speed: number;
    phase: AgentPhase | string; // Allow string in case backend sends something new
    market_context: Record<string, any> | null;
    current_setup: Record<string, any> | null;
    pending_setups: Array<Record<string, any>>;
    open_positions: Array<Record<string, any>>;
    closed_trades: Array<Record<string, any>>;
    starting_balance: number;
    balance: number;
    equity: number;
    total_pnl: number;
    win_count: number;
    loss_count: number;
    trades_this_session: number;
    max_trades_per_session: number;
    can_trade: boolean;
    win_rate: number;
    // Backtest specific
    current_bar_index?: number | null;
    total_bars?: number | null;
    progress?: number | null;
}

export interface SessionStatusResponse {
    state: SessionState;
    reliability: ReliabilityStatus;
    logs: TickLog[];
    audit_log: AuditLogEntry[];
}
