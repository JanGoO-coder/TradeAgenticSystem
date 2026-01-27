"use client";

import { useQuery } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getHealth, getDecisions, getPerformanceMetrics, getSimulatedTrades, DecisionRecord, PerformanceMetrics, SimulatedTrade } from "@/lib/api";
import { History as HistoryIcon, TrendingUp, TrendingDown, XCircle, Clock, BarChart3 } from "lucide-react";

function MetricsCard({ metrics }: { metrics: PerformanceMetrics | undefined }) {
    if (!metrics || metrics.total_trades === 0) {
        return (
            <Card className="bg-slate-900 border-slate-800">
                <CardContent className="py-6 text-center">
                    <BarChart3 className="w-10 h-10 mx-auto mb-2 text-slate-600" />
                    <p className="text-slate-500 text-sm">No trades recorded yet</p>
                </CardContent>
            </Card>
        );
    }
    return (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Card className="bg-slate-900 border-slate-800">
                <CardContent className="pt-4 pb-4">
                    <div className="text-xs text-slate-400">Total Trades</div>
                    <div className="text-2xl font-bold text-slate-100">{metrics.total_trades}</div>
                </CardContent>
            </Card>
            <Card className="bg-slate-900 border-slate-800">
                <CardContent className="pt-4 pb-4">
                    <div className="text-xs text-slate-400">Win Rate</div>
                    <div className={`text-2xl font-bold ${metrics.win_rate >= 50 ? "text-emerald-400" : "text-red-400"}`}>{metrics.win_rate.toFixed(1)}%</div>
                </CardContent>
            </Card>
            <Card className="bg-slate-900 border-slate-800">
                <CardContent className="pt-4 pb-4">
                    <div className="text-xs text-slate-400">Total P&L</div>
                    <div className={`text-2xl font-bold ${metrics.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>{metrics.total_pnl >= 0 ? "+" : ""}{metrics.total_pnl.toFixed(2)}</div>
                </CardContent>
            </Card>
            <Card className="bg-slate-900 border-slate-800">
                <CardContent className="pt-4 pb-4">
                    <div className="text-xs text-slate-400">Profit Factor</div>
                    <div className={`text-2xl font-bold ${metrics.profit_factor >= 1 ? "text-emerald-400" : "text-red-400"}`}>{metrics.profit_factor.toFixed(2)}</div>
                </CardContent>
            </Card>
        </div>
    );
}

function DecisionsList({ decisions }: { decisions: DecisionRecord[] | undefined }) {
    if (!decisions || decisions.length === 0) {
        return (
            <Card className="bg-slate-900 border-slate-800">
                <CardContent className="py-6 text-center">
                    <Clock className="w-10 h-10 mx-auto mb-2 text-slate-600" />
                    <p className="text-slate-500 text-sm">No decisions recorded yet</p>
                </CardContent>
            </Card>
        );
    }
    return (
        <Card className="bg-slate-900 border-slate-800">
            <CardHeader className="pb-2"><CardTitle className="text-sm text-slate-400">Recent Decisions</CardTitle></CardHeader>
            <CardContent>
                <div className="space-y-2 max-h-[400px] overflow-y-auto">
                    {decisions.map((d) => (
                        <div key={d.id} className="flex items-center gap-2 p-2 bg-slate-800/50 rounded-lg">
                            <div className={`w-7 h-7 rounded-full flex items-center justify-center ${d.status === "TRADE_NOW" ? "bg-emerald-500/20" : d.status === "WAIT" ? "bg-yellow-500/20" : "bg-slate-500/20"}`}>
                                {d.status === "TRADE_NOW" ? <TrendingUp className="w-3.5 h-3.5 text-emerald-400" /> : d.status === "WAIT" ? <Clock className="w-3.5 h-3.5 text-yellow-400" /> : <XCircle className="w-3.5 h-3.5 text-slate-400" />}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-1.5"><span className="font-medium text-sm text-slate-100">{d.symbol}</span><Badge variant="outline" className="text-[10px]">{d.status.replace("_", " ")}</Badge></div>
                                <p className="text-xs text-slate-500 truncate">{d.reason}</p>
                            </div>
                            <div className="text-right">
                                <Badge className={`text-[10px] ${d.action_taken === "APPROVED" ? "bg-emerald-500/20 text-emerald-400" : d.action_taken === "REJECTED" ? "bg-red-500/20 text-red-400" : "bg-slate-500/20 text-slate-400"}`}>{d.action_taken}</Badge>
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

function TradesList({ trades }: { trades: SimulatedTrade[] | undefined }) {
    if (!trades || trades.length === 0) {
        return (
            <Card className="bg-slate-900 border-slate-800">
                <CardContent className="py-6 text-center">
                    <TrendingUp className="w-10 h-10 mx-auto mb-2 text-slate-600" />
                    <p className="text-slate-500 text-sm">No simulated trades yet</p>
                </CardContent>
            </Card>
        );
    }
    return (
        <Card className="bg-slate-900 border-slate-800">
            <CardHeader className="pb-2"><CardTitle className="text-sm text-slate-400">Simulated Trades</CardTitle></CardHeader>
            <CardContent>
                <div className="space-y-2 max-h-[400px] overflow-y-auto">
                    {trades.map((t) => (
                        <div key={t.id} className="flex items-center gap-2 p-2 bg-slate-800/50 rounded-lg">
                            <div className={`w-7 h-7 rounded-full flex items-center justify-center ${t.direction === "LONG" ? "bg-emerald-500/20" : "bg-red-500/20"}`}>
                                {t.direction === "LONG" ? <TrendingUp className="w-3.5 h-3.5 text-emerald-400" /> : <TrendingDown className="w-3.5 h-3.5 text-red-400" />}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-1.5"><span className="font-medium text-sm text-slate-100">{t.symbol}</span><Badge variant="outline" className="text-[10px]">{t.direction}</Badge></div>
                                <p className="text-xs text-slate-500">Entry: {t.entry_price.toFixed(5)}</p>
                            </div>
                            <div className="text-right">
                                <Badge className={`text-[10px] ${t.status === "OPEN" ? "bg-blue-500/20 text-blue-400" : t.status === "CLOSED_WIN" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>{t.status.replace("_", " ")}</Badge>
                                {t.pnl !== null && <div className={`text-xs font-medium ${t.pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>{t.pnl >= 0 ? "+" : ""}{t.pnl.toFixed(2)}</div>}
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

export default function HistoryPage() {
    const { data: health } = useQuery({ queryKey: ["health"], queryFn: getHealth });
    const { data: decisions } = useQuery({ queryKey: ["decisions"], queryFn: () => getDecisions(50), refetchInterval: 5000 });
    const { data: metrics } = useQuery({ queryKey: ["metrics"], queryFn: getPerformanceMetrics, refetchInterval: 5000 });
    const { data: trades } = useQuery({ queryKey: ["trades"], queryFn: getSimulatedTrades, refetchInterval: 5000 });

    return (
        <div className="flex flex-col h-full w-full overflow-hidden">
            <Header mode={health?.mode || "ANALYSIS_ONLY"} agentAvailable={health?.agent_available || false} />
            <div className="flex-1 overflow-y-auto">
                <div className="p-4 min-w-0">
                    <div className="flex items-center gap-3 mb-4">
                        <HistoryIcon className="w-5 h-5 text-slate-400" />
                        <h2 className="text-lg font-semibold text-slate-100">Trade History</h2>
                    </div>
                    <div className="mb-4"><MetricsCard metrics={metrics} /></div>
                    <Tabs defaultValue="decisions" className="w-full">
                        <TabsList className="bg-slate-800 mb-3">
                            <TabsTrigger value="decisions" className="text-sm">Decisions</TabsTrigger>
                            <TabsTrigger value="trades" className="text-sm">Trades</TabsTrigger>
                        </TabsList>
                        <TabsContent value="decisions"><DecisionsList decisions={decisions} /></TabsContent>
                        <TabsContent value="trades"><TradesList trades={trades} /></TabsContent>
                    </Tabs>
                </div>
            </div>
        </div>
    );
}
