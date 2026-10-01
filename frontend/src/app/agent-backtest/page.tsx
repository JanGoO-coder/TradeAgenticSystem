"use client";

import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import {
    createBacktestSession,
    getBacktestSession,
    stepForward,
    stepBackward,
    getBacktestResults,
    getEquityCurve,
    BacktestSession,
    BacktestResults,
    AgentDecision,
    getMode,
    getBacktestMT5Status,
    connectMT5,
    HubCallMetrics,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    ArrowLeft,
    Play,
    Pause,
    SkipBack,
    SkipForward,
    Brain,
    TrendingUp,
    Target,
    Wifi,
    WifiOff,
    RefreshCw,
    AlertTriangle
} from "lucide-react";
import Link from "next/link";

// Components
import { ReasoningPanel } from "@/components/analysis/ReasoningPanel";
import { EquityCurveChart } from "@/components/backtest/EquityCurveChart";

export default function AgentBacktestPage() {
    // Config state
    const [symbol, setSymbol] = useState("EURUSD");
    const [fromDate, setFromDate] = useState(() => {
        const date = new Date();
        date.setDate(date.getDate() - 7);
        return date.toISOString().split('T')[0];
    });
    const [toDate, setToDate] = useState(new Date().toISOString().split('T')[0]);

    // UI state
    const [isPlaying, setIsPlaying] = useState(false);
    const [speed, setSpeed] = useState(1);
    const [currentDecision, setCurrentDecision] = useState<AgentDecision | null>(null);
    const [hubStatus, setHubStatus] = useState<'pending' | 'active' | 'no-trade' | null>(null);
    const [hubConfluences, setHubConfluences] = useState<string[]>([]);
    const [hubVetoes, setHubVetoes] = useState<string[]>([]);
    const [hubCallMetrics, setHubCallMetrics] = useState<HubCallMetrics | null>(null);
    const [createError, setCreateError] = useState<string | null>(null);

    // MT5 Status query
    const { data: mt5Status, refetch: refetchMT5Status } = useQuery({
        queryKey: ["backtestMT5Status"],
        queryFn: getBacktestMT5Status,
        refetchInterval: 10000, // Check every 10 seconds
        retry: false,
    });

    // MT5 Connect mutation
    const connectMutation = useMutation({
        mutationFn: connectMT5,
        onSuccess: () => {
            refetchMT5Status();
            setCreateError(null);
        },
        onError: (error: Error) => {
            setCreateError(`Failed to connect to MT5: ${error.message}`);
        }
    });

    // Session query
    const { data: session, refetch: refetchSession } = useQuery<BacktestSession | null>({
        queryKey: ["agentBacktestSession"],
        queryFn: getBacktestSession,
        retry: false,
        refetchOnWindowFocus: false,
        throwOnError: false,
    });

    // Results query
    const { data: results, refetch: refetchResults } = useQuery<BacktestResults>({
        queryKey: ["agentBacktestResults"],
        queryFn: getBacktestResults,
        enabled: !!session,
        refetchInterval: isPlaying ? 2000 : false,
    });

    // Equity curve query
    const { data: equityCurve } = useQuery({
        queryKey: ["agentEquityCurve"],
        queryFn: getEquityCurve,
        enabled: !!session && (results?.trades_count ?? 0) > 0,
        refetchInterval: isPlaying ? 5000 : false,
    });

    // Create session mutation
    const createMutation = useMutation({
        mutationFn: () => createBacktestSession(
            symbol,
            new Date(fromDate),
            new Date(toDate)
        ),
        onSuccess: () => {
            refetchSession();
            refetchResults();
            setCurrentDecision(null);
            setCreateError(null);
        },
        onError: (error: Error) => {
            setCreateError(error.message);
        }
    });

    // Rate limit error state
    const [rateLimitError, setRateLimitError] = useState<string | null>(null);

    // Step forward mutation
    const stepForwardMutation = useMutation({
        mutationFn: (bars: number) => stepForward(bars),
        onSuccess: async (result) => {
            setRateLimitError(null);
            refetchSession();
            if (typeof result.hub_status === 'string') {
                const normalized = result.hub_status.toLowerCase();
                if (normalized === 'pending' || normalized === 'active' || normalized === 'no-trade') {
                    setHubStatus(normalized);
                }
            }
            if (Array.isArray(result.confluences)) {
                setHubConfluences(result.confluences.filter((x): x is string => typeof x === 'string'));
            }
            if (Array.isArray(result.vetoes)) {
                setHubVetoes(result.vetoes.filter((x): x is string => typeof x === 'string'));
            }
            if (result.call_metrics && typeof result.call_metrics === 'object') {
                const cm = result.call_metrics as Partial<HubCallMetrics>;
                setHubCallMetrics({
                    llm_calls: Number(cm.llm_calls ?? 0),
                    subagent_calls: Number(cm.subagent_calls ?? 0),
                    tool_calls: Number(cm.tool_calls ?? 0),
                    cache_hits: Number(cm.cache_hits ?? 0),
                    cache_misses: Number(cm.cache_misses ?? 0),
                });
            }
            if (result.decision) {
                const decisionObj = result.decision as AgentDecision;
                const extra = (decisionObj as unknown as { extra?: { hub_decision?: { reason?: string; confluences?: string[]; vetoes?: string[]; status?: string; llm_called?: boolean; call_metrics?: Partial<HubCallMetrics> } } }).extra;
                if (extra?.hub_decision) {
                    const hd = extra.hub_decision;
                    if (typeof hd.reason === 'string') {
                        decisionObj.brief_reason = hd.reason;
                    }
                    if (Array.isArray(hd.confluences)) {
                        decisionObj.rule_citations = hd.confluences.slice(0, 8);
                    }
                    if (typeof hd.status === 'string') {
                        const s = hd.status.toLowerCase();
                        if (s === 'pending' || s === 'active' || s === 'no-trade') {
                            setHubStatus(s);
                        }
                    }
                    if (typeof hd.llm_called === 'boolean' || hd.call_metrics) {
                        const cm = hd.call_metrics ?? {};
                        setHubCallMetrics({
                            llm_calls: Number(cm.llm_calls ?? 0),
                            subagent_calls: Number(cm.subagent_calls ?? 0),
                            tool_calls: Number(cm.tool_calls ?? 0),
                            cache_hits: Number(cm.cache_hits ?? 0),
                            cache_misses: Number(cm.cache_misses ?? 0),
                        });
                    }
                }
                setCurrentDecision(decisionObj);
            }
            refetchResults();
        },
        onError: (error: Error) => {
            const msg = error.message.toLowerCase();
            if (error.message.includes('429') || msg.includes('rate limit')) {
                setRateLimitError('LLM API rate limit exceeded. Please wait a few seconds before continuing.');
                setIsPlaying(false);
            } else if (msg.includes('cannot reach backend') || msg.includes('failed to fetch') || msg.includes('err_connection_refused')) {
                setRateLimitError('Backend API is unreachable on port 8000. Start/restart FastAPI backend and try again.');
                setIsPlaying(false);
            } else {
                setRateLimitError(error.message);
            }
        }
    });

    // Step backward mutation
    const stepBackwardMutation = useMutation({
        mutationFn: (bars: number) => stepBackward(bars),
        onSuccess: () => {
            refetchSession();
            setCurrentDecision(null);
        },
    });

    // Auto-play effect
    useEffect(() => {
        if (!isPlaying || !session || stepForwardMutation.isPending || rateLimitError) {
            if (rateLimitError && isPlaying) {
                setIsPlaying(false);
            }
            return;
        }

        const interval = setInterval(() => {
            if (session.current_index < session.total_candles - 1) {
                stepForwardMutation.mutate(1);
            } else {
                setIsPlaying(false);
            }
        }, 1000 / speed);

        return () => clearInterval(interval);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isPlaying, session, speed, stepForwardMutation.isPending, rateLimitError]);

    // Keyboard shortcuts
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.target instanceof HTMLInputElement) return;
            if (!session) return;

            switch (e.code) {
                case "Space":
                    e.preventDefault();
                    setIsPlaying(p => !p);
                    break;
                case "ArrowRight":
                    e.preventDefault();
                    if (!stepForwardMutation.isPending) {
                        stepForwardMutation.mutate(e.shiftKey ? 5 : 1);
                    }
                    break;
                case "ArrowLeft":
                    e.preventDefault();
                    if (!stepBackwardMutation.isPending) {
                        stepBackwardMutation.mutate(e.shiftKey ? 5 : 1);
                    }
                    break;
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [session]);

    // Mode query
    const { data: modeData } = useQuery({
        queryKey: ["mode"],
        queryFn: getMode,
        staleTime: 30000,
    });

    const hasSession = !!session && session.status !== 'ERROR';
    const progress = session?.progress ?? 0;

    return (
        <div className="min-h-screen bg-slate-950">
            <Header mode={modeData?.mode || "ANALYSIS_ONLY"} agentAvailable={true} />

            <main className="container mx-auto px-4 py-6">
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-4">
                        <Link href="/">
                            <Button variant="ghost" size="icon">
                                <ArrowLeft className="w-4 h-4" />
                            </Button>
                        </Link>
                        <div>
                            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                                <Brain className="w-6 h-6 text-purple-400" />
                                Agent Backtest
                            </h1>
                            <p className="text-slate-400 text-sm">
                                Time-machine backtesting with LLM reasoning
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        {/* MT5 Status Badge */}
                        {mt5Status?.connected ? (
                            <Badge className="bg-green-600/20 text-green-400 border border-green-600/30 flex items-center gap-1.5">
                                <Wifi className="w-3 h-3" />
                                MT5 Connected
                            </Badge>
                        ) : (
                            <Badge className="bg-red-600/20 text-red-400 border border-red-600/30 flex items-center gap-1.5">
                                <WifiOff className="w-3 h-3" />
                                MT5 Disconnected
                            </Badge>
                        )}

                        {hasSession && (
                            <Badge variant={session.status === 'RUNNING' ? 'default' : 'secondary'}>
                                {session.status.toUpperCase()}
                            </Badge>
                        )}
                    </div>
                </div>

                {/* Configuration Panel */}
                {!hasSession && (
                    <div className="bg-slate-800 rounded-lg p-6 mb-6">
                        {/* MT5 Connection Status Bar */}
                        <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-700">
                            <div className="flex items-center gap-3">
                                <h2 className="text-lg font-semibold text-white">Configure Backtest</h2>
                                <span className="text-slate-500 text-sm">|</span>
                                <span className="text-sm text-slate-400">
                                    Data Source: <span className="text-purple-400 font-medium">MT5 Historical</span>
                                </span>
                            </div>
                            {!mt5Status?.connected && (
                                <Button
                                    onClick={() => connectMutation.mutate()}
                                    disabled={connectMutation.isPending}
                                    size="sm"
                                    className="bg-green-600 hover:bg-green-700"
                                >
                                    {connectMutation.isPending ? (
                                        <>
                                            <RefreshCw className="w-3 h-3 mr-1.5 animate-spin" />
                                            Connecting...
                                        </>
                                    ) : (
                                        <>
                                            <Wifi className="w-3 h-3 mr-1.5" />
                                            Connect MT5
                                        </>
                                    )}
                                </Button>
                            )}
                        </div>

                        {/* Error Message */}
                        {createError && (
                            <div className="mb-4 p-4 bg-red-900/30 border border-red-600/30 rounded-lg flex items-start gap-3">
                                <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                                <div>
                                    <p className="text-red-400 font-medium">Failed to create session</p>
                                    <p className="text-red-300/80 text-sm mt-1">{createError}</p>
                                </div>
                            </div>
                        )}

                        <div className="grid grid-cols-4 gap-4">
                            <div>
                                <label className="text-sm text-slate-400 block mb-1">Symbol</label>
                                <select
                                    value={symbol}
                                    onChange={(e) => setSymbol(e.target.value)}
                                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white"
                                >
                                    <option value="EURUSD">EURUSD</option>
                                    <option value="GBPUSD">GBPUSD</option>
                                    <option value="XAUUSD">XAUUSD</option>
                                </select>
                            </div>
                            <div>
                                <label className="text-sm text-slate-400 block mb-1">From</label>
                                <input
                                    type="date"
                                    value={fromDate}
                                    onChange={(e) => setFromDate(e.target.value)}
                                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white"
                                />
                            </div>
                            <div>
                                <label className="text-sm text-slate-400 block mb-1">To</label>
                                <input
                                    type="date"
                                    value={toDate}
                                    onChange={(e) => setToDate(e.target.value)}
                                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white"
                                />
                            </div>
                            <div className="flex items-end">
                                <Button
                                    onClick={() => {
                                        setCreateError(null);
                                        createMutation.mutate();
                                    }}
                                    disabled={createMutation.isPending || !mt5Status?.connected}
                                    className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-50"
                                >
                                    {createMutation.isPending ? 'Creating...' : 'Start Backtest'}
                                </Button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Main Content */}
                {hasSession && (
                    <div className="space-y-6">
                        {/* Control Bar */}
                        <div className="bg-slate-800 rounded-lg p-4">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="flex items-center gap-2">
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            onClick={() => stepBackwardMutation.mutate(5)}
                                            disabled={stepBackwardMutation.isPending}
                                        >
                                            <SkipBack className="w-4 h-4" />
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            onClick={() => stepBackwardMutation.mutate(1)}
                                            disabled={stepBackwardMutation.isPending}
                                        >
                                            <ArrowLeft className="w-4 h-4" />
                                        </Button>

                                        <Button
                                            size="icon"
                                            onClick={() => setIsPlaying(p => !p)}
                                            className={isPlaying ? 'bg-yellow-600' : 'bg-green-600'}
                                        >
                                            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                                        </Button>

                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            onClick={() => stepForwardMutation.mutate(1)}
                                            disabled={stepForwardMutation.isPending}
                                        >
                                            <SkipForward className="w-4 h-4" />
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            onClick={() => stepForwardMutation.mutate(5)}
                                            disabled={stepForwardMutation.isPending}
                                        >
                                            <SkipForward className="w-4 h-4" />
                                        </Button>
                                    </div>

                                    {/* Speed Control */}
                                    <div className="flex items-center gap-2 border-l border-slate-700 pl-4">
                                        <span className="text-slate-400 text-sm">Speed:</span>
                                        {[1, 2, 5, 10].map(s => (
                                            <Button
                                                key={s}
                                                variant={speed === s ? 'default' : 'ghost'}
                                                size="sm"
                                                onClick={() => setSpeed(s)}
                                                className="w-8"
                                            >
                                                {s}x
                                            </Button>
                                        ))}
                                    </div>
                                </div>

                                {/* Progress */}
                                <div className="flex items-center gap-4">
                                    <div className="text-slate-400 text-sm">
                                        Bar {session.current_index + 1} / {session.total_candles}
                                    </div>
                                    <div className="w-48 bg-slate-700 rounded-full h-2">
                                        <div
                                            className="bg-purple-500 h-2 rounded-full transition-all"
                                            style={{ width: `${progress * 100}%` }}
                                        />
                                    </div>
                                    <span className="text-white font-mono">
                                        {(progress * 100).toFixed(1)}%
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Rate Limit Error */}
                        {rateLimitError && (
                            <div className="bg-yellow-900/50 border border-yellow-600 rounded-lg p-4 flex items-start gap-3">
                                <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5 shrink-0" />
                                <div>
                                    <p className="text-yellow-200 font-medium">API Rate Limit Reached</p>
                                    <p className="text-yellow-300/80 text-sm mt-1">{rateLimitError}</p>
                                    <p className="text-yellow-300/60 text-xs mt-2">Wait a moment before continuing. The LLM service will retry automatically.</p>
                                </div>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setRateLimitError(null)}
                                    className="ml-auto text-yellow-400 hover:text-yellow-200"
                                >
                                    Dismiss
                                </Button>
                            </div>
                        )}

                        {/* Stats Bar */}
                        {results && (
                            <div className="grid grid-cols-6 gap-4">
                                <StatCard
                                    label="Trades"
                                    value={results.trades_count.toString()}
                                    icon={<Target className="w-4 h-4 text-blue-400" />}
                                />
                                <StatCard
                                    label="Win Rate"
                                    value={`${(results.performance.win_rate * 100).toFixed(1)}%`}
                                    icon={<TrendingUp className="w-4 h-4 text-green-400" />}
                                    valueColor={results.performance.win_rate >= 0.5 ? 'text-green-400' : 'text-red-400'}
                                />
                                <StatCard
                                    label="Total P&L"
                                    value={`${results.performance.total_pnl_r > 0 ? '+' : ''}${results.performance.total_pnl_r.toFixed(2)}R`}
                                    icon={<TrendingUp className="w-4 h-4 text-purple-400" />}
                                    valueColor={results.performance.total_pnl_r >= 0 ? 'text-green-400' : 'text-red-400'}
                                />
                                <StatCard
                                    label="Max DD"
                                    value={`${results.performance.max_drawdown_r.toFixed(2)}R`}
                                    icon={<TrendingUp className="w-4 h-4 text-red-400" />}
                                    valueColor="text-red-400"
                                />
                                <StatCard
                                    label="Expectancy"
                                    value={`${results.performance.expectancy_r.toFixed(2)}R`}
                                    icon={<Target className="w-4 h-4 text-yellow-400" />}
                                    valueColor={results.performance.expectancy_r >= 0 ? 'text-green-400' : 'text-red-400'}
                                />
                                <StatCard
                                    label="Decisions"
                                    value={results.decisions_count.toString()}
                                    icon={<Brain className="w-4 h-4 text-purple-400" />}
                                />
                            </div>
                        )}

                        {hubStatus && (
                            <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                                <div className="flex flex-wrap items-center gap-2 mb-3">
                                    <span className="text-xs uppercase tracking-wide text-slate-500">Hub Status</span>
                                    <Badge className={
                                        hubStatus === 'active'
                                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                                            : hubStatus === 'pending'
                                                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                                                : 'bg-slate-500/20 text-slate-300 border border-slate-500/40'
                                    }>
                                        {hubStatus.toUpperCase()}
                                    </Badge>
                                    {hubCallMetrics && (
                                        <>
                                            <span className="text-xs text-slate-400">LLM calls: {hubCallMetrics.llm_calls}</span>
                                            <span className="text-xs text-slate-400">Cache hits: {hubCallMetrics.cache_hits}</span>
                                            <span className="text-xs text-slate-400">Sub-agent calls: {hubCallMetrics.subagent_calls}</span>
                                        </>
                                    )}
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    <div className="p-2 rounded bg-slate-900 border border-slate-700">
                                        <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Confluences</div>
                                        <div className="text-xs text-slate-300">
                                            {hubConfluences.length ? hubConfluences.join(', ') : 'none'}
                                        </div>
                                    </div>
                                    <div className="p-2 rounded bg-slate-900 border border-slate-700">
                                        <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Vetoes</div>
                                        <div className="text-xs text-slate-300">
                                            {hubVetoes.length ? hubVetoes.join(', ') : 'none'}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Main Grid */}
                        <div className="grid grid-cols-2 gap-6">
                            {/* Reasoning Panel */}
                            <ReasoningPanel
                                decision={currentDecision}
                                isLoading={stepForwardMutation.isPending}
                            />

                            {/* Equity Curve */}
                            {equityCurve && equityCurve.curve.length > 0 ? (
                                <EquityCurveChart
                                    data={equityCurve.curve}
                                    maxDrawdownR={equityCurve.max_drawdown_r}
                                    totalPnlR={equityCurve.total_pnl_r}
                                />
                            ) : (
                                <div className="bg-slate-800 rounded-lg p-4 flex items-center justify-center">
                                    <span className="text-slate-500">
                                        Equity curve will appear after trades
                                    </span>
                                </div>
                            )}
                        </div>

                        {/* Trade List */}
                        {results && results.trades.length > 0 && (
                            <div className="bg-slate-800 rounded-lg p-4">
                                <h3 className="text-lg font-semibold text-white mb-4">Trades</h3>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-slate-400 border-b border-slate-700">
                                                <th className="text-left py-2">Time</th>
                                                <th className="text-left py-2">Direction</th>
                                                <th className="text-right py-2">Entry</th>
                                                <th className="text-right py-2">SL</th>
                                                <th className="text-right py-2">Exit</th>
                                                <th className="text-center py-2">Status</th>
                                                <th className="text-right py-2">P&L</th>
                                                <th className="text-left py-2">Rules</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {results.trades.map((trade, i) => (
                                                <tr key={i} className="border-b border-slate-700/50">
                                                    <td className="py-2 text-slate-300">
                                                        {new Date(trade.entry_time).toLocaleString()}
                                                    </td>
                                                    <td className={`py-2 ${trade.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}`}>
                                                        {trade.direction}
                                                    </td>
                                                    <td className="py-2 text-right text-white">
                                                        {trade.entry_price.toFixed(5)}
                                                    </td>
                                                    <td className="py-2 text-right text-red-400">
                                                        {trade.stop_loss.toFixed(5)}
                                                    </td>
                                                    <td className="py-2 text-right text-white">
                                                        {trade.exit_price?.toFixed(5) ?? '-'}
                                                    </td>
                                                    <td className="py-2 text-center">
                                                        <Badge variant={
                                                            trade.status === 'won' ? 'default' :
                                                                trade.status === 'lost' ? 'destructive' :
                                                                    'secondary'
                                                        }>
                                                            {trade.status.toUpperCase()}
                                                        </Badge>
                                                    </td>
                                                    <td className={`py-2 text-right ${(trade.pnl_r ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
                                                        }`}>
                                                        {trade.pnl_r ? `${trade.pnl_r > 0 ? '+' : ''}${trade.pnl_r.toFixed(2)}R` : '-'}
                                                    </td>
                                                    <td className="py-2">
                                                        <div className="flex gap-1">
                                                            {(trade.rule_citations ?? []).slice(0, 2).map((rule, j) => (
                                                                <span key={j} className="px-1 bg-purple-900/50 text-purple-300 rounded text-xs">
                                                                    {rule}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}

// Stat Card Component
function StatCard({
    label,
    value,
    icon,
    valueColor = 'text-white'
}: {
    label: string;
    value: string;
    icon: React.ReactNode;
    valueColor?: string;
}) {
    return (
        <div className="bg-slate-800 rounded-lg p-4">
            <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
                {icon}
                {label}
            </div>
            <div className={`text-xl font-bold ${valueColor}`}>
                {value}
            </div>
        </div>
    );
}
