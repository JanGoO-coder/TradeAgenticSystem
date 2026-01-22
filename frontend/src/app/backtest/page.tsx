"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import { TradingPairSelector } from "@/components/dashboard/TradingPairSelector";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { getHealth, analyzeMarket, TradeSetupResponse } from "@/lib/api";
import {
    Play,
    Pause,
    SkipForward,
    SkipBack,
    RotateCcw,
    Loader2,
    Calendar,
    ArrowLeft,
    ChevronRight,
    ChevronLeft,
    Database
} from "lucide-react";
import Link from "next/link";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Speed options for playback
const speedOptions = [
    { value: 1, label: "1x" },
    { value: 2, label: "2x" },
    { value: 5, label: "5x" },
    { value: 10, label: "10x" },
];

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

export default function BacktestPage() {
    const queryClient = useQueryClient();
    const [selectedPair, setSelectedPair] = useState("EURUSD");
    const [fromDate, setFromDate] = useState(() => {
        const date = new Date();
        date.setDate(date.getDate() - 7); // 1 week ago
        return date.toISOString().split('T')[0];
    });
    const [toDate, setToDate] = useState(() => new Date().toISOString().split('T')[0]);
    const [speed, setSpeed] = useState(1);
    const [isPlaying, setIsPlaying] = useState(false);
    const [analysisResult, setAnalysisResult] = useState<TradeSetupResponse | null>(null);

    const { data: health } = useQuery({
        queryKey: ["health"],
        queryFn: getHealth,
        refetchInterval: 5000,
    });

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
                    symbol: selectedPair,
                    from_date: new Date(fromDate).toISOString(),
                    to_date: new Date(toDate).toISOString(),
                    timeframes: ["1H", "15M", "5M"]
                }),
            });
            if (!res.ok) throw new Error("Failed to load backtest data");
            return res.json();
        },
        onSuccess: () => {
            refetchStatus();
            setAnalysisResult(null);
        },
    });

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
            // Auto-run analysis on step
            if (data.snapshot) {
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
        onSuccess: () => refetchStatus(),
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
        },
    });

    // Run analysis on current snapshot
    const runAnalysis = async (snapshot: BacktestSnapshot) => {
        try {
            const marketData = {
                symbol: snapshot.symbol,
                timestamp: snapshot.timestamp,
                timeframe_bars: snapshot.timeframe_bars,
                account_balance: 10000.0,
                risk_pct: 1.0,
                economic_calendar: []
            };
            const result = await analyzeMarket(marketData);
            setAnalysisResult(result);
        } catch (error) {
            console.error("Analysis failed:", error);
        }
    };

    // Playback effect
    const handlePlay = () => {
        setIsPlaying(true);
    };

    const handlePause = () => {
        setIsPlaying(false);
    };

    // Auto-step when playing
    const handleAutoStep = () => {
        if (isPlaying && backtestStatus?.loaded && !stepMutation.isPending) {
            if (backtestStatus.current_index < backtestStatus.total_bars - 1) {
                stepMutation.mutate(1);
            } else {
                setIsPlaying(false);
            }
        }
    };

    // Use effect for auto-stepping would go here in a real implementation
    // For now, manual stepping only

    const isLoaded = backtestStatus?.loaded || false;
    const progress = backtestStatus?.progress || 0;

    return (
        <div className="flex flex-col h-full w-full overflow-hidden">
            <Header
                mode={health?.mode || "ANALYSIS_ONLY"}
                agentAvailable={health?.agent_available || false}
            />

            <ScrollArea className="flex-1">
                <div className="p-4 min-w-0">
                    {/* Header */}
                    <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                        <div className="flex items-center gap-2">
                            <Link href="/">
                                <Button variant="ghost" size="icon" className="h-8 w-8">
                                    <ArrowLeft className="w-4 h-4" />
                                </Button>
                            </Link>
                            <h2 className="text-lg font-semibold text-slate-100">Backtest Mode</h2>
                            <Badge variant="outline" className="bg-yellow-500/20 text-yellow-400 border-yellow-500/50">
                                <Database className="w-3 h-3 mr-1" />
                                Simulation
                            </Badge>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                        {/* Left: Configuration Panel */}
                        <Card className="bg-slate-900 border-slate-800">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base flex items-center gap-2">
                                    <Calendar className="w-4 h-4 text-blue-400" />
                                    Backtest Configuration
                                </CardTitle>
                                <CardDescription className="text-sm">
                                    Select symbol and date range for backtesting
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {/* Symbol Selection */}
                                <div className="space-y-2">
                                    <Label className="text-sm text-slate-300">Symbol</Label>
                                    <TradingPairSelector
                                        value={selectedPair}
                                        onChange={setSelectedPair}
                                        className="w-full"
                                    />
                                </div>

                                {/* Date Range */}
                                <div className="grid grid-cols-2 gap-3">
                                    <div className="space-y-2">
                                        <Label className="text-xs text-slate-400">From Date</Label>
                                        <Input
                                            type="date"
                                            value={fromDate}
                                            onChange={(e) => setFromDate(e.target.value)}
                                            className="bg-slate-800 border-slate-700"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label className="text-xs text-slate-400">To Date</Label>
                                        <Input
                                            type="date"
                                            value={toDate}
                                            onChange={(e) => setToDate(e.target.value)}
                                            className="bg-slate-800 border-slate-700"
                                        />
                                    </div>
                                </div>

                                {/* Load Button */}
                                <Button
                                    onClick={() => loadMutation.mutate()}
                                    disabled={loadMutation.isPending}
                                    className="w-full bg-blue-600 hover:bg-blue-700"
                                >
                                    {loadMutation.isPending ? (
                                        <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Loading...</>
                                    ) : (
                                        <><Database className="w-4 h-4 mr-2" />Load Data</>
                                    )}
                                </Button>

                                <Separator className="bg-slate-800" />

                                {/* Speed Control */}
                                <div className="space-y-2">
                                    <Label className="text-sm text-slate-300">Playback Speed</Label>
                                    <Select
                                        value={String(speed)}
                                        onValueChange={(v) => setSpeed(parseInt(v))}
                                    >
                                        <SelectTrigger className="bg-slate-800 border-slate-700">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {speedOptions.map((opt) => (
                                                <SelectItem key={opt.value} value={String(opt.value)}>
                                                    {opt.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Middle: Playback Controls & Progress */}
                        <Card className="bg-slate-900 border-slate-800">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base">Playback Controls</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {/* Progress Bar */}
                                <div className="space-y-2">
                                    <div className="flex justify-between text-xs text-slate-400">
                                        <span>Progress</span>
                                        <span>{progress.toFixed(1)}%</span>
                                    </div>
                                    <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-gradient-to-r from-blue-500 to-emerald-500 transition-all duration-300"
                                            style={{ width: `${progress}%` }}
                                        />
                                    </div>
                                    <div className="flex justify-between text-xs text-slate-500">
                                        <span>Bar {backtestStatus?.current_index || 0}</span>
                                        <span>of {backtestStatus?.total_bars || 0}</span>
                                    </div>
                                </div>

                                {/* Control Buttons */}
                                <div className="flex items-center justify-center gap-2">
                                    <Button
                                        variant="outline"
                                        size="icon"
                                        onClick={() => resetMutation.mutate()}
                                        disabled={!isLoaded || resetMutation.isPending}
                                        className="border-slate-700"
                                    >
                                        <RotateCcw className="w-4 h-4" />
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="icon"
                                        onClick={() => stepBackMutation.mutate(1)}
                                        disabled={!isLoaded || stepBackMutation.isPending}
                                        className="border-slate-700"
                                    >
                                        <SkipBack className="w-4 h-4" />
                                    </Button>
                                    <Button
                                        size="lg"
                                        onClick={isPlaying ? handlePause : handlePlay}
                                        disabled={!isLoaded}
                                        className={isPlaying ? "bg-yellow-600 hover:bg-yellow-700" : "bg-emerald-600 hover:bg-emerald-700"}
                                    >
                                        {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="icon"
                                        onClick={() => stepMutation.mutate(1)}
                                        disabled={!isLoaded || stepMutation.isPending}
                                        className="border-slate-700"
                                    >
                                        <SkipForward className="w-4 h-4" />
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="icon"
                                        onClick={() => stepMutation.mutate(5)}
                                        disabled={!isLoaded || stepMutation.isPending}
                                        className="border-slate-700"
                                    >
                                        <ChevronRight className="w-4 h-4" />
                                        <ChevronRight className="w-4 h-4 -ml-2" />
                                    </Button>
                                </div>

                                {/* Status */}
                                <div className="text-center">
                                    {!isLoaded ? (
                                        <p className="text-sm text-slate-500">Load data to begin backtesting</p>
                                    ) : (
                                        <p className="text-sm text-slate-400">
                                            {backtestStatus?.symbol} | {backtestStatus?.from_date?.split('T')[0]} to {backtestStatus?.to_date?.split('T')[0]}
                                        </p>
                                    )}
                                </div>
                            </CardContent>
                        </Card>

                        {/* Right: Analysis Results */}
                        <Card className="bg-slate-900 border-slate-800">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base">Analysis Results</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {analysisResult ? (
                                    <div className="space-y-3">
                                        {/* Status */}
                                        <div className="flex items-center gap-2">
                                            <Badge
                                                className={
                                                    analysisResult.status === "TRADE_NOW"
                                                        ? "bg-emerald-500/20 text-emerald-400"
                                                        : analysisResult.status === "WAIT"
                                                            ? "bg-yellow-500/20 text-yellow-400"
                                                            : "bg-slate-500/20 text-slate-400"
                                                }
                                            >
                                                {analysisResult.status}
                                            </Badge>
                                            <span className="text-sm text-slate-400">{analysisResult.reason_short}</span>
                                        </div>

                                        {/* Bias */}
                                        <div className="grid grid-cols-2 gap-2 text-sm">
                                            <div className="bg-slate-800 rounded p-2">
                                                <div className="text-xs text-slate-500">HTF Bias</div>
                                                <div className={
                                                    analysisResult.htf_bias.value === "BULLISH"
                                                        ? "text-emerald-400 font-medium"
                                                        : analysisResult.htf_bias.value === "BEARISH"
                                                            ? "text-red-400 font-medium"
                                                            : "text-slate-400"
                                                }>
                                                    {analysisResult.htf_bias.value}
                                                </div>
                                            </div>
                                            <div className="bg-slate-800 rounded p-2">
                                                <div className="text-xs text-slate-500">Confidence</div>
                                                <div className="text-slate-100 font-medium">{analysisResult.confidence}%</div>
                                            </div>
                                        </div>

                                        {/* Setup */}
                                        {analysisResult.setup.name !== "NO_SETUP" && (
                                            <div className="bg-slate-800 rounded p-2">
                                                <div className="text-xs text-slate-500">Setup</div>
                                                <div className="text-slate-100">{analysisResult.setup.name}</div>
                                                <div className="text-xs text-slate-400 mt-1">
                                                    Confluence: {analysisResult.setup.confluence_score}
                                                </div>
                                            </div>
                                        )}

                                        {/* Explanation */}
                                        <div className="text-xs text-slate-400 bg-slate-800/50 rounded p-2">
                                            {analysisResult.explanation}
                                        </div>
                                    </div>
                                ) : (
                                    <div className="text-center text-slate-500 py-8">
                                        <p className="text-sm">Step through data to see analysis</p>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </ScrollArea>
        </div>
    );
}
