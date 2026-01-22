"use client";

import { useState, useEffect, useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import { 
    getHealth, 
    analyzeMarket, 
    TradeSetupResponse, 
    getMT5Status, 
    getMT5Symbols, 
    connectMT5 
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Keyboard } from "lucide-react";
import Link from "next/link";

// Backtest components
import { CandlestickChart } from "@/components/backtest/CandlestickChart";
import { BacktestControlBar } from "@/components/backtest/BacktestControlBar";
import { BacktestAnalysisPanel } from "@/components/backtest/BacktestAnalysisPanel";
import { BacktestStatsBar } from "@/components/backtest/BacktestStatsBar";
import { BacktestConfigSheet } from "@/components/backtest/BacktestConfigSheet";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface BacktestStatus {
    loaded: boolean;
    running: boolean;
    symbol: string | null;
    from_date: string | null;
    to_date: string | null;
    current_index: number;
    total_bars: number;
    progress: number;
}

interface BacktestSnapshot {
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

interface BacktestConfig {
    symbol: string;
    fromDate: string;
    toDate: string;
    timeframes: string[];
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
    }));
    
    // UI state
    const [configOpen, setConfigOpen] = useState(false);
    const [selectedTimeframe, setSelectedTimeframe] = useState("1H");
    const [speed, setSpeed] = useState(1);
    const [isPlaying, setIsPlaying] = useState(false);
    const [analysisResult, setAnalysisResult] = useState<TradeSetupResponse | null>(null);
    const [dataSource, setDataSource] = useState<"mt5" | "sample">("sample");
    const [currentSnapshot, setCurrentSnapshot] = useState<BacktestSnapshot | null>(null);

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
            }).catch(() => {});
        }
    }, [mt5Status?.available, mt5Status?.connected, queryClient]);

    // Backtest status query
    const { data: backtestStatus, refetch: refetchStatus } = useQuery<BacktestStatus>({
        queryKey: ["backtestStatus"],
        queryFn: async () => {
            const res = await fetch(`${API_BASE_URL}/api/v1/market-data/backtest/status`);
            if (!res.ok) throw new Error("Failed to fetch backtest status");
            return res.json();
        },
        refetchInterval: isPlaying ? 1000 / speed : false,
    });

    // Load backtest data mutation
    const loadMutation = useMutation({
        mutationFn: async () => {
            const res = await fetch(`${API_BASE_URL}/api/v1/market-data/backtest/load`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: config.symbol,
                    from_date: new Date(config.fromDate).toISOString(),
                    to_date: new Date(config.toDate).toISOString(),
                    timeframes: config.timeframes,
                }),
            });
            if (!res.ok) throw new Error("Failed to load backtest data");
            return res.json();
        },
        onSuccess: (data) => {
            refetchStatus();
            setAnalysisResult(null);
            setDataSource(data.source === "mt5" ? "mt5" : "sample");
            // Fetch initial snapshot
            fetchSnapshot();
        },
    });

    // Fetch snapshot
    const fetchSnapshot = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/v1/market-data/backtest/snapshot`);
            if (res.ok) {
                const snapshot = await res.json();
                setCurrentSnapshot(snapshot);
            }
        } catch (error) {
            console.error("Failed to fetch snapshot:", error);
        }
    };

    // Step forward mutation
    const stepMutation = useMutation({
        mutationFn: async (bars: number = 1) => {
            const res = await fetch(`${API_BASE_URL}/api/v1/market-data/backtest/step`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bars }),
            });
            if (!res.ok) throw new Error("Failed to step backtest");
            return res.json();
        },
        onSuccess: (data) => {
            refetchStatus();
            if (data.snapshot) {
                setCurrentSnapshot(data.snapshot);
                runAnalysis(data.snapshot);
            }
        },
    });

    // Step backward mutation
    const stepBackMutation = useMutation({
        mutationFn: async (bars: number = 1) => {
            const res = await fetch(`${API_BASE_URL}/api/v1/market-data/backtest/step-back`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bars }),
            });
            if (!res.ok) throw new Error("Failed to step back");
            return res.json();
        },
        onSuccess: (data) => {
            refetchStatus();
            if (data.snapshot) {
                setCurrentSnapshot(data.snapshot);
            }
        },
    });

    // Reset mutation
    const resetMutation = useMutation({
        mutationFn: async () => {
            const res = await fetch(`${API_BASE_URL}/api/v1/market-data/backtest/reset`, {
                method: 'POST',
            });
            if (!res.ok) throw new Error("Failed to reset backtest");
            return res.json();
        },
        onSuccess: () => {
            refetchStatus();
            setAnalysisResult(null);
            setIsPlaying(false);
            fetchSnapshot();
        },
    });

    // Jump to mutation
    const jumpMutation = useMutation({
        mutationFn: async (index: number) => {
            const res = await fetch(`${API_BASE_URL}/api/v1/market-data/backtest/jump`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ index }),
            });
            if (!res.ok) throw new Error("Failed to jump");
            return res.json();
        },
        onSuccess: (data) => {
            refetchStatus();
            if (data.snapshot) {
                setCurrentSnapshot(data.snapshot);
            }
        },
    });

    // Run analysis
    const runAnalysis = async (snapshot: BacktestSnapshot) => {
        try {
            const marketData = {
                symbol: snapshot.symbol,
                timestamp: snapshot.timestamp,
                timeframe_bars: snapshot.timeframe_bars,
                account_balance: 10000.0,
                risk_pct: 1.0,
                economic_calendar: [],
            };
            const result = await analyzeMarket(marketData);
            setAnalysisResult(result);
        } catch (error) {
            console.error("Analysis failed:", error);
        }
    };

    // Playback controls
    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    // Auto-step when playing
    useEffect(() => {
        if (!isPlaying || !backtestStatus?.loaded || stepMutation.isPending) return;
        
        const interval = setInterval(() => {
            if (backtestStatus.current_index < backtestStatus.total_bars - 1) {
                stepMutation.mutate(1);
            } else {
                setIsPlaying(false);
            }
        }, 1000 / speed);

        return () => clearInterval(interval);
    }, [isPlaying, backtestStatus?.loaded, backtestStatus?.current_index, backtestStatus?.total_bars, speed, stepMutation.isPending]);

    // Keyboard shortcuts
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Ignore if typing in an input
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
            
            const isLoaded = backtestStatus?.loaded;
            if (!isLoaded) return;

            switch (e.code) {
                case "Space":
                    e.preventDefault();
                    if (isPlaying) handlePause();
                    else handlePlay();
                    break;
                case "ArrowRight":
                    e.preventDefault();
                    if (!stepMutation.isPending) {
                        stepMutation.mutate(e.shiftKey ? 5 : 1);
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
    }, [isPlaying, backtestStatus?.loaded, stepMutation.isPending, stepBackMutation.isPending]);

    // Derived state
    const isLoaded = backtestStatus?.loaded || false;
    const progress = backtestStatus?.progress || 0;
    const chartData = currentSnapshot?.timeframe_bars || {};

    // Price levels for chart
    const priceLevels = analysisResult?.setup?.entry_price ? [
        { price: analysisResult.setup.entry_price, label: "Entry", type: "entry" as const },
        ...(analysisResult.setup.stop_loss ? [{ price: analysisResult.setup.stop_loss, label: "SL", type: "stop" as const }] : []),
        ...(analysisResult.setup.take_profit?.[0] ? [{ price: analysisResult.setup.take_profit[0], label: "TP", type: "target" as const }] : []),
    ] : [];

    // Get current timestamp from snapshot
    const currentTimestamp = currentSnapshot?.timeframe_bars?.["1H"]?.slice(-1)?.[0]?.timestamp;

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
                isLoading={loadMutation.isPending}
                totalBars={backtestStatus?.total_bars || 0}
                onConfigClick={() => setConfigOpen(true)}
                onLoadClick={() => loadMutation.mutate()}
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

                {/* Analysis Panel (Right - 30%) */}
                <div className="w-[320px] flex-shrink-0 border-l border-slate-800 bg-slate-950">
                    <BacktestAnalysisPanel 
                        analysis={analysisResult} 
                        className="h-full"
                    />
                </div>
            </div>

            {/* Bottom Control Bar */}
            <BacktestControlBar
                isLoaded={isLoaded}
                isPlaying={isPlaying}
                currentIndex={backtestStatus?.current_index || 0}
                totalBars={backtestStatus?.total_bars || 0}
                progress={progress}
                speed={speed}
                currentTimestamp={currentTimestamp}
                onPlay={handlePlay}
                onPause={handlePause}
                onStepForward={(bars) => stepMutation.mutate(bars)}
                onStepBack={(bars) => stepBackMutation.mutate(bars)}
                onReset={() => resetMutation.mutate()}
                onJumpTo={(index) => jumpMutation.mutate(index)}
                onSpeedChange={setSpeed}
                isSteppingForward={stepMutation.isPending}
                isSteppingBack={stepBackMutation.isPending}
                isResetting={resetMutation.isPending}
            />

            {/* Config Sheet */}
            <BacktestConfigSheet
                open={configOpen}
                onOpenChange={setConfigOpen}
                config={config}
                onConfigChange={setConfig}
                onApply={() => loadMutation.mutate()}
                mt5Symbols={mt5SymbolsData?.symbols}
            />
        </div>
    );
}
