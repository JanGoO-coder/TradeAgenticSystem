"use client";

import { useState, useEffect, useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import {
    getHealth,
    getMT5Status,
    getMT5Symbols,
    connectMT5,
    OrderRequest,
    // New unified session API
    initSession,
    getBacktestSessionState,
    advanceTime,
    getSessionStatistics,
    analyzeCurrentBar,
    downloadBacktestResults,
    BacktestSessionState,
    SessionStatistics,
    HierarchicalPosition,
    HierarchicalClosedTrade,
    InitSessionRequest,
    AdvanceTimeResponse,
    TradeSetupResponse,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Keyboard, PanelRightOpen, PanelRightClose } from "lucide-react";
import Link from "next/link";

// Backtest components
import { CandlestickChart } from "@/components/backtest/CandlestickChart";
import { BacktestControlBar } from "@/components/backtest/BacktestControlBar";
import { BacktestAnalysisPanel } from "@/components/backtest/BacktestAnalysisPanel";
import { BacktestStatsBar } from "@/components/backtest/BacktestStatsBar";
import { BacktestConfigSheet } from "@/components/backtest/BacktestConfigSheet";
import { BacktestTradePanel } from "@/components/backtest/BacktestTradePanel";
import { TradeConfirmDialog } from "@/components/backtest/TradeConfirmDialog";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface BacktestConfig {
    symbol: string;
    fromDate: string;
    toDate: string;
    timeframes: string[];
    initialBalance?: number;
    riskPerTrade?: number;
}

interface ChartSnapshot {
    symbol: string;
    timestamp: string;
    current_index: number;
    total_bars: number;
    progress: number;
    timeframe_bars: Record<string, Array<{
        timestamp: string;
        open: number;
        high: number;
        low: number;
        close: number;
        volume: number;
    }>>;
}

export default function BacktestPage() {
    const queryClient = useQueryClient();

    // Config state
    const [config, setConfig] = useState<BacktestConfig>(() => ({
        symbol: "EURUSD",
        fromDate: (() => {
            const date = new Date();
            date.setDate(date.getDate() - 7);
            return date.toISOString().split('T')[0];
        })(),
        toDate: new Date().toISOString().split('T')[0],
        timeframes: ["1H", "15M", "5M"],
        initialBalance: 10000,
        riskPerTrade: 1.0,
    }));

    // UI state
    const [configOpen, setConfigOpen] = useState(false);
    const [selectedTimeframe, setSelectedTimeframe] = useState("1H");
    const [speed, setSpeed] = useState(1);
    const [isPlaying, setIsPlaying] = useState(false);
    const [analysisResult, setAnalysisResult] = useState<TradeSetupResponse | null>(null);
    const [dataSource, setDataSource] = useState<"mt5" | "sample">("sample");
    const [chartSnapshot, setChartSnapshot] = useState<ChartSnapshot | null>(null);

    // Trade panel state
    const [tradePanelOpen, setTradePanelOpen] = useState(false);
    const [tradeConfirmOpen, setTradeConfirmOpen] = useState(false);
    const [pendingOrder, setPendingOrder] = useState<Partial<OrderRequest> | null>(null);
    const [isExporting, setIsExporting] = useState(false);

    // Health query
    const { data: health } = useQuery({
        queryKey: ["health"],
        queryFn: getHealth,
        refetchInterval: 5000,
    });

    // MT5 Status query
    const { data: mt5Status } = useQuery({
        queryKey: ["mt5Status"],
        queryFn: getMT5Status,
        refetchInterval: 10000,
    });

    // MT5 Symbols query
    const { data: mt5SymbolsData } = useQuery({
        queryKey: ["mt5Symbols"],
        queryFn: getMT5Symbols,
        enabled: mt5Status?.connected === true,
        staleTime: 60000,
    });

    // Auto-connect to MT5 on page load
    useEffect(() => {
        if (mt5Status?.available && !mt5Status?.connected) {
            connectMT5().then(() => {
                queryClient.invalidateQueries({ queryKey: ["mt5Status"] });
                queryClient.invalidateQueries({ queryKey: ["mt5Symbols"] });
            }).catch(() => { });
        }
    }, [mt5Status?.available, mt5Status?.connected, queryClient]);

    // Session state query (replaces backtest status)
    const { data: sessionState, refetch: refetchSession } = useQuery<BacktestSessionState | null>({
        queryKey: ["sessionState"],
        queryFn: getBacktestSessionState,
        refetchInterval: isPlaying ? 1000 / speed : 2000,
    });

    // Session statistics query
    const { data: sessionStatistics } = useQuery<SessionStatistics>({
        queryKey: ["sessionStatistics"],
        queryFn: getSessionStatistics,
        enabled: sessionState?.mode === 'BACKTEST',
        refetchInterval: 2000,
    });

    // Export handler
    const handleExport = async () => {
        setIsExporting(true);
        try {
            await downloadBacktestResults();
        } catch (error) {
            console.error("Export failed:", error);
        } finally {
            setIsExporting(false);
        }
    };

    // Initialize session mutation (replaces load backtest)
    const initMutation = useMutation({
        mutationFn: async () => {
            const request: InitSessionRequest = {
                symbol: config.symbol,
                mode: 'BACKTEST',
                start_time: new Date(config.fromDate).toISOString(),
                end_time: new Date(config.toDate).toISOString(),
                starting_balance: config.initialBalance,
                timeframes: config.timeframes,
            };
            return initSession(request);
        },
        onSuccess: async (data) => {
            refetchSession();
            setAnalysisResult(null);
            setDataSource("mt5");  // Session API uses MT5 data
            // Fetch initial chart data
            fetchChartSnapshot();
            // Advance a few bars to get initial data and run analysis
            try {
                await advanceTime({ bars: 10, tick_mode: false });
                fetchChartSnapshot();
                runAnalysis();
            } catch (e) {
                console.error("Initial advance failed:", e);
            }
        },
    });

    // Fetch chart snapshot from backtest service (for chart data)
    const fetchChartSnapshot = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/v1/session/snapshot`);
            if (res.ok) {
                const snapshot = await res.json();
                setChartSnapshot(snapshot);
            }
        } catch (error) {
            console.error("Failed to fetch chart snapshot:", error);
        }
    };

    // Advance time mutation (replaces step forward)
    const advanceMutation = useMutation({
        mutationFn: async (bars: number = 1) => {
            return advanceTime({ bars, tick_mode: false });
        },
        onSuccess: (data) => {
            refetchSession();
            fetchChartSnapshot();
            // Run analysis after advancing
            runAnalysis();
        },
    });

    // Step backward mutation (still uses backtest service for now)
    const stepBackMutation = useMutation({
        mutationFn: async (bars: number = 1) => {
            const res = await fetch(`${API_BASE_URL}/api/v1/session/step-back`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bars }),
            });
            if (!res.ok) throw new Error("Failed to step back");
            return res.json();
        },
        onSuccess: (data) => {
            refetchSession();
            fetchChartSnapshot();
        },
    });

    // Reset mutation
    const resetMutation = useMutation({
        mutationFn: async () => {
            const res = await fetch(`${API_BASE_URL}/api/v1/session/reset`, {
                method: 'POST',
            });
            if (!res.ok) throw new Error("Failed to reset backtest");
            return res.json();
        },
        onSuccess: () => {
            refetchSession();
            setAnalysisResult(null);
            setIsPlaying(false);
            fetchChartSnapshot();
        },
    });

    // Jump to mutation
    const jumpMutation = useMutation({
        mutationFn: async (index: number) => {
            const res = await fetch(`${API_BASE_URL}/api/v1/session/jump`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ index }),
            });
            if (!res.ok) throw new Error("Failed to jump");
            return res.json();
        },
        onSuccess: (data) => {
            refetchSession();
            fetchChartSnapshot();
        },
    });

    // Run analysis using session API
    const runAnalysis = async () => {
        try {
            const result = await analyzeCurrentBar();
            // The API returns { success: bool, analysis: {...}, error?: string }
            if (result.success && result.analysis) {
                setAnalysisResult(result.analysis as unknown as TradeSetupResponse);
            } else if (!result.success) {
                console.warn("Analysis error:", result.error);
            }
        } catch (error) {
            console.error("Analysis failed:", error);
        }
    };

    // Playback controls
    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    // Auto-step when playing
    useEffect(() => {
        if (!isPlaying || !sessionState?.mode || advanceMutation.isPending) return;
        if (sessionState.mode !== 'BACKTEST') return;

        const interval = setInterval(() => {
            const currentIndex = sessionState.current_bar_index ?? 0;
            const totalBars = sessionState.total_bars ?? 0;
            if (currentIndex < totalBars - 1) {
                advanceMutation.mutate(1);
            } else {
                setIsPlaying(false);
            }
        }, 1000 / speed);

        return () => clearInterval(interval);
    }, [isPlaying, sessionState?.mode, sessionState?.current_bar_index, sessionState?.total_bars, speed, advanceMutation.isPending]);

    // Keyboard shortcuts
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Ignore if typing in an input
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

            const isLoaded = sessionState?.mode === 'BACKTEST';
            if (!isLoaded) return;

            switch (e.code) {
                case "Space":
                    e.preventDefault();
                    if (isPlaying) handlePause();
                    else handlePlay();
                    break;
                case "ArrowRight":
                    e.preventDefault();
                    if (!advanceMutation.isPending) {
                        advanceMutation.mutate(e.shiftKey ? 5 : 1);
                    }
                    break;
                case "ArrowLeft":
                    e.preventDefault();
                    if (!stepBackMutation.isPending) {
                        stepBackMutation.mutate(e.shiftKey ? 5 : 1);
                    }
                    break;
                case "Home":
                    e.preventDefault();
                    resetMutation.mutate();
                    break;
                case "Digit1":
                    setSpeed(1);
                    break;
                case "Digit2":
                    setSpeed(2);
                    break;
                case "Digit5":
                    setSpeed(5);
                    break;
                case "Digit0":
                    setSpeed(10);
                    break;
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isPlaying, sessionState?.mode, advanceMutation.isPending, stepBackMutation.isPending]);

    // Derived state
    const isLoaded = sessionState?.mode === 'BACKTEST';
    const currentIndex = sessionState?.current_bar_index ?? 0;
    const totalBars = sessionState?.total_bars ?? 0;
    const progress = totalBars > 0 ? (currentIndex / totalBars) * 100 : 0;
    const chartData = chartSnapshot?.timeframe_bars || {};

    // Convert session statistics to backtest statistics format for stats bar
    const backtestStatistics = sessionStatistics ? {
        total_trades: sessionStatistics.total_trades,
        winners: sessionStatistics.winners,
        losers: sessionStatistics.losers,
        win_rate: sessionStatistics.win_rate,
        profit_factor: sessionStatistics.profit_factor,
        total_pnl_pips: sessionStatistics.total_pnl_pips,
        total_pnl_usd: sessionStatistics.total_pnl_usd,
        gross_profit_pips: sessionStatistics.gross_profit_pips,
        gross_loss_pips: sessionStatistics.gross_loss_pips,
        max_drawdown_pips: sessionStatistics.max_drawdown_pips,
        average_rr: sessionStatistics.average_rr,
        largest_win_pips: sessionStatistics.largest_win_pips,
        largest_loss_pips: sessionStatistics.largest_loss_pips,
        average_win_pips: sessionStatistics.average_win_pips,
        average_loss_pips: sessionStatistics.average_loss_pips,
        consecutive_wins: sessionStatistics.consecutive_wins,
        consecutive_losses: sessionStatistics.consecutive_losses,
        current_balance: sessionStatistics.current_balance,
        starting_balance: sessionStatistics.starting_balance,
    } : null;

    // Price levels for chart
    const priceLevels = analysisResult?.setup?.entry_price ? [
        { price: analysisResult.setup.entry_price, label: "Entry", type: "entry" as const },
        ...(analysisResult.setup.stop_loss ? [{ price: analysisResult.setup.stop_loss, label: "SL", type: "stop" as const }] : []),
        ...(analysisResult.setup.take_profit?.[0] ? [{ price: analysisResult.setup.take_profit[0], label: "TP", type: "target" as const }] : []),
    ] : [];

    // Get current timestamp from snapshot - use the selected timeframe's last candle
    const currentTimestamp = chartSnapshot?.timeframe_bars?.[selectedTimeframe]?.slice(-1)?.[0]?.timestamp
        || sessionState?.current_time
        || chartSnapshot?.timestamp;

    return (
        <div className="flex flex-col h-screen w-full overflow-hidden bg-slate-950">
            {/* Header */}
            <Header
                mode={health?.mode || "ANALYSIS_ONLY"}
                agentAvailable={health?.agent_available || false}
            />

            {/* Top Stats Bar */}
            <BacktestStatsBar
                symbol={config.symbol}
                fromDate={config.fromDate}
                toDate={config.toDate}
                dataSource={dataSource}
                isLoaded={isLoaded}
                isLoading={initMutation.isPending}
                totalBars={totalBars}
                statistics={backtestStatistics}
                onConfigClick={() => setConfigOpen(true)}
                onLoadClick={() => initMutation.mutate()}
                onExportClick={handleExport}
                isExporting={isExporting}
            />

            {/* Main Content Area */}
            <div className="flex-1 flex overflow-hidden">
                {/* Chart Area (Left - 70%) */}
                <div className="flex-1 flex flex-col p-3 overflow-hidden">
                    {/* Back button and title */}
                    <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                            <Link href="/">
                                <Button variant="ghost" size="icon" className="h-7 w-7">
                                    <ArrowLeft className="w-4 h-4" />
                                </Button>
                            </Link>
                            <h1 className="text-sm font-semibold text-slate-100">Backtest God View</h1>
                            <Badge variant="outline" className="bg-yellow-500/20 text-yellow-400 border-yellow-500/50 text-xs">
                                SIMULATION
                            </Badge>
                        </div>

                        {/* Keyboard shortcuts hint */}
                        <TooltipProvider>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <Button variant="ghost" size="sm" className="h-7 text-xs text-slate-500">
                                        <Keyboard className="w-3.5 h-3.5 mr-1" />
                                        Shortcuts
                                    </Button>
                                </TooltipTrigger>
                                <TooltipContent side="bottom" className="bg-slate-900 border-slate-700 text-xs">
                                    <div className="space-y-1">
                                        <div><kbd className="bg-slate-800 px-1 rounded">Space</kbd> Play/Pause</div>
                                        <div><kbd className="bg-slate-800 px-1 rounded">→</kbd> Step forward</div>
                                        <div><kbd className="bg-slate-800 px-1 rounded">←</kbd> Step back</div>
                                        <div><kbd className="bg-slate-800 px-1 rounded">Shift+→/←</kbd> Skip 5 bars</div>
                                        <div><kbd className="bg-slate-800 px-1 rounded">Home</kbd> Reset</div>
                                        <div><kbd className="bg-slate-800 px-1 rounded">1/2/5/0</kbd> Speed presets</div>
                                    </div>
                                </TooltipContent>
                            </Tooltip>
                        </TooltipProvider>

                        {/* Trade Panel Toggle */}
                        <TooltipProvider>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <Button
                                        variant={tradePanelOpen ? "secondary" : "ghost"}
                                        size="sm"
                                        className="h-7 text-xs"
                                        onClick={() => setTradePanelOpen(!tradePanelOpen)}
                                    >
                                        {tradePanelOpen ? (
                                            <PanelRightClose className="w-3.5 h-3.5 mr-1" />
                                        ) : (
                                            <PanelRightOpen className="w-3.5 h-3.5 mr-1" />
                                        )}
                                        Trading
                                    </Button>
                                </TooltipTrigger>
                                <TooltipContent side="bottom" className="bg-slate-900 border-slate-700 text-xs">
                                    Toggle trading panel
                                </TooltipContent>
                            </Tooltip>
                        </TooltipProvider>
                    </div>

                    {/* Chart */}
                    <CandlestickChart
                        data={chartData}
                        selectedTimeframe={selectedTimeframe}
                        onTimeframeChange={setSelectedTimeframe}
                        priceLevels={priceLevels}
                        symbol={config.symbol}
                        className="flex-1"
                    />
                </div>

                {/* Analysis Panel (Right) */}
                <div className="w-[320px] flex-shrink-0 border-l border-slate-800 bg-slate-950">
                    <BacktestAnalysisPanel
                        analysis={analysisResult}
                        className="h-full"
                        onExecuteTrade={analysisResult?.setup?.entry_price ? () => {
                            // Build order from analysis
                            const setup = analysisResult.setup;
                            const order: Partial<OrderRequest> = {
                                symbol: analysisResult.symbol,
                                order_type: setup.type === 'LONG' ? 'MARKET_BUY' : 'MARKET_SELL',
                                stop_loss: setup.stop_loss || 0,
                                take_profit: setup.take_profit?.[0],
                                price: setup.entry_price || 0,
                            };
                            setPendingOrder(order);
                            setTradeConfirmOpen(true);
                        } : undefined}
                    />
                </div>

                {/* Trade Panel (Far Right - Collapsible) */}
                {tradePanelOpen && (
                    <div className="w-[300px] flex-shrink-0 border-l border-slate-800 bg-slate-950">
                        <BacktestTradePanel
                            className="h-full"
                            isBacktestLoaded={isLoaded}
                        />
                    </div>
                )}
            </div>

            {/* Bottom Control Bar */}
            <BacktestControlBar
                isLoaded={isLoaded}
                isPlaying={isPlaying}
                currentIndex={currentIndex}
                totalBars={totalBars}
                progress={progress}
                speed={speed}
                currentTimestamp={currentTimestamp}
                onPlay={handlePlay}
                onPause={handlePause}
                onStepForward={(bars) => advanceMutation.mutate(bars)}
                onStepBack={(bars) => stepBackMutation.mutate(bars)}
                onReset={() => resetMutation.mutate()}
                onJumpTo={(index) => jumpMutation.mutate(index)}
                onSpeedChange={setSpeed}
                isSteppingForward={advanceMutation.isPending}
                isSteppingBack={stepBackMutation.isPending}
                isResetting={resetMutation.isPending}
            />

            {/* Config Sheet */}
            <BacktestConfigSheet
                open={configOpen}
                onOpenChange={setConfigOpen}
                config={config}
                onConfigChange={setConfig}
                onApply={() => initMutation.mutate()}
                mt5Symbols={mt5SymbolsData?.symbols}
            />

            {/* Trade Confirmation Dialog */}
            <TradeConfirmDialog
                open={tradeConfirmOpen}
                onOpenChange={setTradeConfirmOpen}
                order={pendingOrder}
                backtestMode={true}
                onSuccess={(response) => {
                    if (response.success) {
                        // Toast notification for successful trade
                        console.log('Trade executed:', response);
                        // Invalidate queries to refresh positions
                        queryClient.invalidateQueries({ queryKey: ['sessionState'] });
                        queryClient.invalidateQueries({ queryKey: ['sessionStatistics'] });
                    }
                    setPendingOrder(null);
                }}
                onError={(error) => {
                    console.error('Trade failed:', error);
                    setPendingOrder(null);
                }}
            />
        </div>
    );
}
