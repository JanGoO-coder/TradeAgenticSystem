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
import {
    getHealth,
    getSession,
    getDataConfig,
    TradeSetupResponse,
    createMT5MarketData,
    getMT5Status,
    connectMT5,
    getHubDecision,
    HubDecisionResponse,
} from "@/lib/api";
import { Play, Loader2, ArrowLeft, Radio, Circle, AlertCircle } from "lucide-react";
import Link from "next/link";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function MonitorPage() {
    const [selectedPair, setSelectedPair] = useState("EURUSD");
    const [currentSetup, setCurrentSetup] = useState<TradeSetupResponse | null>(null);
    const [hubDecision, setHubDecision] = useState<HubDecisionResponse | null>(null);
    const [isLiveMode, setIsLiveMode] = useState(false);
    const [liveConnected, setLiveConnected] = useState(false);
    const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const queryClient = useQueryClient();

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
            const hub = await getHubDecision({
                symbol: selectedPair,
                timestamp: typeof marketData.timestamp === "string" ? marketData.timestamp : new Date().toISOString(),
                timeframe_bars: marketData.timeframe_bars as Record<string, Array<{ timestamp: string; open: number; high: number; low: number; close: number; volume: number }>>,
                account_balance: 10000.0,
                risk_pct: 0.5,
                economic_calendar: [],
            });
            return { hub };
        },
        onSuccess: ({ hub }) => {
            setHubDecision(hub);
            setCurrentSetup({
                symbol: hub.symbol,
                timestamp: hub.timestamp,
                status: hub.status === "active" ? "TRADE_NOW" : hub.status === "pending" ? "WAIT" : "NO_TRADE",
                reason_short: hub.reason,
                htf_bias: {
                    value: (hub.bias || "neutral").toUpperCase() as "BULLISH" | "BEARISH" | "NEUTRAL",
                    rule_refs: ["1.1"],
                },
                ltf_alignment: {
                    timeframe: "15M",
                    alignment: hub.confluences.includes("poi_aligned") ? "ALIGNED" : "NOT_ALIGNED",
                    rule_refs: ["1.2"],
                },
                setup: {
                    name: hub.poi ? "ICT_HUB_SETUP" : "NO_SETUP",
                    type: "ICT_HUB",
                    entry_price: hub.entry,
                    entry_type: hub.entry !== null ? "LIMIT" : null,
                    stop_loss: hub.sl,
                    take_profit: hub.tp !== null ? [hub.tp] : null,
                    invalidation_point: hub.sl,
                    is_counter_trend: false,
                    confluence_score: Math.min(10, hub.confluences.length + (hub.status === "active" ? 2 : 0)),
                    rule_refs: [...hub.confluences, ...hub.vetoes],
                },
                risk: {
                    account_balance: Number((hub.metadata?.risk as { account_balance?: number } | undefined)?.account_balance ?? 10000),
                    risk_pct: Number((hub.metadata?.risk as { risk_pct?: number } | undefined)?.risk_pct ?? 0.5),
                    position_size: hub.size ?? 0,
                    rr: hub.rr,
                },
                checklist: {
                    htf_bias_exists: hub.confluences.includes("htf_bias_confirmed"),
                    ltf_mss: hub.confluences.includes("displacement_detected"),
                    pd_alignment: hub.confluences.includes("poi_aligned"),
                    liquidity_sweep_detected: hub.confluences.includes("liquidity_draw_identified"),
                    session_ok: hub.confluences.includes("killzone_valid") && !hub.vetoes.includes("outside_utc_killzone"),
                    news_ok: !hub.vetoes.some((v) => v.includes("news")),
                    rr_minimum_met: hub.confluences.includes("rr_gate_passed"),
                },
                explanation: hub.reason,
                graph_nodes_triggered: [...hub.confluences, ...hub.vetoes],
                confidence: hub.status === "active" ? 0.85 : hub.status === "pending" ? 0.6 : 0.35,
            });
        },
    });

    const isMT5Connected = mt5Status?.connected ?? false;

    const closeLiveSocket = useCallback(() => {
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
        setLiveConnected(false);
    }, []);

    const handlePairChange = useCallback((pair: string) => {
        setSelectedPair(pair);
        setCurrentSetup(null);
        setHubDecision(null);
        closeLiveSocket();
    }, [closeLiveSocket]);

    const toggleLiveMode = useCallback(() => {
        setIsLiveMode((prev) => {
            const next = !prev;
            if (!next) {
                closeLiveSocket();
            }
            return next;
        });
    }, [closeLiveSocket]);

    // WebSocket connection for live mode
    const connectLive = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;
        const wsUrl = API_BASE_URL.replace('http', 'ws') + `/ws/live/${selectedPair}`;
        const ws = new WebSocket(wsUrl);
        ws.onopen = () => setLiveConnected(true);
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "analysis" && data.data) {
                setCurrentSetup(data.data as TradeSetupResponse);
                const payload = data.data as Partial<TradeSetupResponse> & { graph_nodes_triggered?: string[] };
                const refs = payload.graph_nodes_triggered ?? [];
                const vetoes = refs.filter((r) => r.includes("veto") || r.includes("outside") || r.includes("limit"));
                const confluences = refs.filter((r) => !vetoes.includes(r));
                setHubDecision({
                    symbol: payload.symbol ?? selectedPair,
                    timestamp: payload.timestamp ?? new Date().toISOString(),
                    bias: payload.htf_bias?.value?.toLowerCase() ?? "neutral",
                    draw: payload.reason_short ?? "none",
                    poi: payload.setup?.name ?? null,
                    entry: payload.setup?.entry_price ?? null,
                    sl: payload.setup?.stop_loss ?? null,
                    tp: payload.setup?.take_profit?.[0] ?? null,
                    rr: payload.risk?.rr ?? null,
                    size: payload.risk?.position_size ?? null,
                    session: session?.kill_zone_name ?? "outside-killzone",
                    status:
                        payload.status === "TRADE_NOW"
                            ? "active"
                            : payload.status === "WAIT"
                                ? "pending"
                                : "no-trade",
                    reason: payload.reason_short ?? "",
                    confluences,
                    vetoes,
                    llm_called: false,
                    cache_hit: false,
                    journal_id: null,
                    call_metrics: {
                        llm_calls: 0,
                        subagent_calls: 0,
                        tool_calls: 0,
                        cache_hits: 0,
                        cache_misses: 0,
                    },
                    metadata: {},
                });
                setLastUpdate(new Date());
            }
        };
        ws.onclose = () => { setLiveConnected(false); wsRef.current = null; };
        ws.onerror = () => setLiveConnected(false);
        wsRef.current = ws;
    }, [selectedPair, session?.kill_zone_name]);

    useEffect(() => {
        if (isLiveMode) {
            connectLive();
        }
        return () => {
            closeLiveSocket();
        };
    }, [isLiveMode, selectedPair, connectLive, closeLiveSocket]);

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
                            <TradingPairSelector value={selectedPair} onChange={handlePairChange} className="w-[160px]" />
                        </div>
                        <div className="flex items-center gap-2">
                            <Button
                                onClick={toggleLiveMode}
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
                            {hubDecision && (
                                <>
                                    <Badge className="text-xs ml-2 bg-sky-500/20 text-sky-300 border-sky-500/40 border">
                                        HUB {hubDecision.status.toUpperCase()}
                                    </Badge>
                                    <span className="text-xs text-slate-400">LLM: {hubDecision.llm_called ? "yes" : "no"}</span>
                                    <span className="text-xs text-slate-400">Cache hits: {hubDecision.call_metrics.cache_hits}</span>
                                </>
                            )}
                        </div>
                    )}

                    {hubDecision && (
                        <div className="mb-4 grid grid-cols-1 lg:grid-cols-3 gap-2">
                            <div className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300">
                                <span className="text-slate-500">Draw:</span> {hubDecision.draw || "none"}
                            </div>
                            <div className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300">
                                <span className="text-slate-500">POI:</span> {hubDecision.poi || "none"}
                            </div>
                            <div className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300">
                                <span className="text-slate-500">Vetoes:</span> {hubDecision.vetoes.length > 0 ? hubDecision.vetoes.join(", ") : "none"}
                            </div>
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
