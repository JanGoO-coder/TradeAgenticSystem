"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import { ScrollArea } from "@/components/ui/scroll-area";
import { getHealth, getSession, analyzeMarket, getDataConfig, TradeSetupResponse, DataConfig, createMT5MarketData, getMT5Status, connectMT5 } from "@/lib/api";
import { Play, Loader2, ArrowLeft, Radio, Circle, AlertCircle } from "lucide-react";
import Link from "next/link";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function MonitorPage() {
    const [selectedPair, setSelectedPair] = useState("EURUSD");
    const [currentSetup, setCurrentSetup] = useState<TradeSetupResponse | null>(null);
    const [isLiveMode, setIsLiveMode] = useState(false);
    const [liveConnected, setLiveConnected] = useState(false);
    const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const queryClient = useQueryClient();

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

    // MT5 Status query
    const { data: mt5Status } = useQuery({
        queryKey: ["mt5Status"],
        queryFn: getMT5Status,
        refetchInterval: 10000,
    });

    // Auto-connect to MT5 on page load
    useEffect(() => {
        if (mt5Status?.available && !mt5Status?.connected) {
            connectMT5().then(() => {
                queryClient.invalidateQueries({ queryKey: ["mt5Status"] });
            }).catch(() => {});
        }
    }, [mt5Status?.available, mt5Status?.connected, queryClient]);

    const analyzeMutation = useMutation({
        mutationFn: async () => {
            // Fetch real MT5 data instead of sample data
            const marketData = await createMT5MarketData(selectedPair, dataConfig);
            return analyzeMarket(marketData);
        },
        onSuccess: (data) => setCurrentSetup(data),
    });

    const isMT5Connected = mt5Status?.connected ?? false;

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
        <div className="flex flex-col h-full w-full">
            <Header mode={health?.mode || "ANALYSIS_ONLY"} agentAvailable={health?.agent_available || false} />

            <ScrollArea className="flex-1 min-h-0">
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
                            <Button onClick={() => analyzeMutation.mutate()} className="bg-emerald-600 hover:bg-emerald-700" disabled={analyzeMutation.isPending || isLiveMode || !isMT5Connected} size="sm">
                                {analyzeMutation.isPending ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Analyzing...</> : <><Play className="w-4 h-4 mr-2" />Analyze {selectedPair}</>}
                            </Button>
                        </div>
                    </div>

                    {/* MT5 Connection Warning */}
                    {!isMT5Connected && (
                        <div className="mb-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg flex items-center gap-2 text-yellow-400 text-sm">
                            <AlertCircle className="w-4 h-4" />
                            <span>MT5 not connected. Ensure MetaTrader 5 is running to analyze live market data.</span>
                        </div>
                    )}

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
            </ScrollArea>
        </div>
    );
}
