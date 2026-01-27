"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import { TradeSetupViewer } from "@/components/analysis/TradeSetupViewer";
import { RuleExplanationPanel } from "@/components/analysis/RuleExplanationPanel";
import { SessionClock } from "@/components/dashboard/SessionClock";
import { BiasCard } from "@/components/dashboard/BiasCard";
import { ConfluenceMeter } from "@/components/dashboard/ConfluenceMeter";
import { ChecklistPanel } from "@/components/dashboard/ChecklistPanel";
import { TradingPairSelector } from "@/components/dashboard/TradingPairSelector";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getHealth, getSession, analyzeMarket, getDataConfig, TradeSetupResponse, DataConfig } from "@/lib/api";
import { Play, Loader2, ArrowLeft, Radio, Circle } from "lucide-react";
import Link from "next/link";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Generate sample market data that varies by symbol and uses config
const createSampleMarketData = (symbol: string, config?: DataConfig) => {
    const seed = symbol.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
    const basePrice = symbol.includes('JPY') ? 150.0 : symbol.includes('XAU') ? 2000.0 : symbol.includes('BTC') ? 45000.0 : 1.08;
    const volatility = symbol.includes('XAU') ? 0.005 : symbol.includes('BTC') ? 0.02 : 0.002;

    // Use config bar counts or defaults
    const htfBars = config?.htf_bars || 50;
    const ltfBars = config?.ltf_bars || 100;
    const microBars = config?.micro_bars || 50;

    const generateBars = (count: number, tf: string) => {
        const bars = [];
        let price = basePrice;
        const trendDirection = (seed % 3) - 1;

        for (let i = 0; i < count; i++) {
            const change = (Math.sin(seed + i) * volatility) + (trendDirection * volatility * 0.3);
            const high = price * (1 + Math.abs(change) + volatility * 0.5);
            const low = price * (1 - Math.abs(change) - volatility * 0.5);
            const close = price * (1 + change);

            bars.push({
                timestamp: new Date(Date.now() - (count - i) * (tf === "1H" ? 3600000 : tf === "15M" ? 900000 : 300000)).toISOString(),
                open: Number(price.toFixed(5)),
                high: Number(high.toFixed(5)),
                low: Number(low.toFixed(5)),
                close: Number(close.toFixed(5)),
                volume: 1000 + (seed % 500) + i * 100
            });
            price = close;
        }
        return bars;
    };

    return {
        symbol,
        timestamp: new Date().toISOString(),
        timeframe_bars: {
            "1H": generateBars(htfBars, "1H"),
            "15M": generateBars(ltfBars, "15M"),
            "5M": generateBars(microBars, "5M")
        },
        account_balance: 10000.0,
        risk_pct: 1.0,
        economic_calendar: []
    };
};

export default function MonitorPage() {
    const [selectedPair, setSelectedPair] = useState("EURUSD");
    const [currentSetup, setCurrentSetup] = useState<TradeSetupResponse | null>(null);
    const [isLiveMode, setIsLiveMode] = useState(false);
    const [liveConnected, setLiveConnected] = useState(false);
    const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
    const wsRef = useRef<WebSocket | null>(null);

    // Clear analysis when pair changes
    useEffect(() => {
        setCurrentSetup(null);
        if (isLiveMode && wsRef.current) {
            wsRef.current.close();
            setLiveConnected(false);
        }
    }, [selectedPair, isLiveMode]);

    const { data: health } = useQuery({ queryKey: ["health"], queryFn: getHealth, refetchInterval: 5000 });
    const { data: session } = useQuery({ queryKey: ["session"], queryFn: getSession, refetchInterval: 1000 });
    const { data: dataConfig } = useQuery({ queryKey: ["dataConfig"], queryFn: getDataConfig, staleTime: 30000 });

    const analyzeMutation = useMutation({
        mutationFn: () => analyzeMarket(createSampleMarketData(selectedPair, dataConfig)),
        onSuccess: (data) => setCurrentSetup(data),
    });

    // WebSocket connection for live mode
    const connectLive = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;
        const wsUrl = API_BASE_URL.replace('http', 'ws') + `/ws/live/${selectedPair}`;
        const ws = new WebSocket(wsUrl);
        ws.onopen = () => setLiveConnected(true);
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "analysis" && data.data) {
                setCurrentSetup(data.data);
                setLastUpdate(new Date());
            }
        };
        ws.onclose = () => { setLiveConnected(false); wsRef.current = null; };
        ws.onerror = () => setLiveConnected(false);
        wsRef.current = ws;
    }, [selectedPair]);

    const disconnectLive = useCallback(() => {
        wsRef.current?.close();
        wsRef.current = null;
        setLiveConnected(false);
    }, []);

    useEffect(() => {
        if (isLiveMode) connectLive();
        else disconnectLive();
        return () => disconnectLive();
    }, [isLiveMode, selectedPair, connectLive, disconnectLive]);

    return (
        <div className="flex flex-col h-full w-full overflow-hidden">
            <Header mode={health?.mode || "ANALYSIS_ONLY"} agentAvailable={health?.agent_available || false} />

            <div className="flex-1 overflow-y-auto">
                <div className="p-4 min-w-0">
                    {/* Header */}
                    <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                        <div className="flex items-center gap-2 flex-wrap">
                            <Link href="/"><Button variant="ghost" size="icon" className="h-8 w-8"><ArrowLeft className="w-4 h-4" /></Button></Link>
                            <h2 className="text-lg font-semibold text-slate-100">Live Monitor</h2>
                            <TradingPairSelector value={selectedPair} onChange={setSelectedPair} className="w-[160px]" />
                        </div>
                        <div className="flex items-center gap-2">
                            <Button
                                onClick={() => setIsLiveMode(!isLiveMode)}
                                variant={isLiveMode ? "default" : "outline"}
                                className={isLiveMode ? "bg-red-600 hover:bg-red-700" : "border-slate-700"}
                                size="sm"
                            >
                                {isLiveMode ? (
                                    <><Radio className="w-4 h-4 mr-2" />{liveConnected ? <span className="flex items-center gap-1.5">Live<span className="relative flex h-2 w-2"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75"></span><span className="relative inline-flex rounded-full h-2 w-2 bg-white"></span></span></span> : "Connecting..."}</>
                                ) : (
                                    <><Circle className="w-4 h-4 mr-2" />Live Off</>
                                )}
                            </Button>
                            <Button onClick={() => analyzeMutation.mutate()} className="bg-emerald-600 hover:bg-emerald-700" disabled={analyzeMutation.isPending || isLiveMode} size="sm">
                                {analyzeMutation.isPending ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Analyzing...</> : <><Play className="w-4 h-4 mr-2" />Analyze {selectedPair}</>}
                            </Button>
                        </div>
                    </div>

                    {/* Current Symbol Display */}
                    {currentSetup && (
                        <div className="mb-4 p-2 bg-slate-800/50 rounded-lg border border-slate-700 flex items-center gap-2">
                            <span className="text-xs text-slate-400">Analyzing:</span>
                            <span className="text-sm font-medium text-emerald-400">{currentSetup.symbol}</span>
                            {isLiveMode && liveConnected && (
                                <>
                                    <Badge className="bg-red-500/20 text-red-400 text-xs ml-2">LIVE</Badge>
                                    {lastUpdate && <span className="text-xs text-slate-400 ml-2">Updated {lastUpdate.toLocaleTimeString()}</span>}
                                </>
                            )}
                        </div>
                    )}

                    {/* Main Grid */}
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                        {/* Left Panel */}
                        <div className="lg:col-span-3 space-y-4">
                            <SessionClock session={session?.session || "Loading..."} killZoneActive={session?.kill_zone_active || false} killZoneName={session?.kill_zone_name || null} currentTimeEst={session?.current_time_est || "00:00"} />
                            <BiasCard bias={currentSetup?.htf_bias.value || "NEUTRAL"} ruleRefs={currentSetup?.htf_bias.rule_refs || ["1.1"]} timeframe="1H" />
                            <BiasCard bias={currentSetup?.ltf_alignment.alignment === "ALIGNED" ? currentSetup.htf_bias.value : "NEUTRAL"} ruleRefs={currentSetup?.ltf_alignment.rule_refs || ["1.2"]} timeframe="15M" />
                            <ConfluenceMeter score={currentSetup?.setup.confluence_score || 0} confidence={currentSetup?.confidence || 0} />
                        </div>

                        {/* Middle Panel */}
                        <div className="lg:col-span-5 space-y-4">
                            <TradeSetupViewer setup={currentSetup} />
                            <ChecklistPanel checklist={currentSetup?.checklist || null} />
                        </div>

                        {/* Right Panel */}
                        <div className="lg:col-span-4">
                            <RuleExplanationPanel checklist={currentSetup?.checklist || null} ruleRefs={currentSetup?.setup.rule_refs || []} explanation={currentSetup?.explanation || "Select a pair and run analysis"} />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
