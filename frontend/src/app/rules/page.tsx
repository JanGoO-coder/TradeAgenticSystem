"use client";

import { useState } from "react";
import { Header } from "@/components/layout/Header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/lib/api";
import { BookOpen, CheckCircle2, ChevronDown, ChevronRight, Target, TrendingUp, Clock, Shield, AlertTriangle, Zap } from "lucide-react";

const rulesData = {
    bias: [
        { id: "1.1", name: "HTF Bias", description: "1H directional bias via HH/HL (bullish) or LH/LL (bearish).", details: "The 1H chart determines overall direction.", importance: "critical" },
        { id: "1.2", name: "LTF Alignment", description: "15M must align with 1H bias direction.", details: "LTF provides entry precision.", importance: "high" },
    ],
    structure: [
        { id: "2.1", name: "Swing Points", description: "Identify swing highs/lows using fractal logic.", details: "Min 2-3 candles lookback.", importance: "critical" },
        { id: "2.3", name: "MSS", description: "Displacement through prior swing signals a shift.", details: "Bullish MSS breaks above swing high with momentum.", importance: "high" },
    ],
    liquidity: [
        { id: "3.4", name: "Liquidity Sweep", description: "Price must sweep liquidity before entry.", details: "Trap sellers before longs, trap buyers before shorts.", importance: "critical" },
        { id: "3.5", name: "Equal Highs/Lows", description: "Equal highs/lows represent liquidity pools.", details: "Stop orders concentrate at these levels.", importance: "medium" },
    ],
    pdArrays: [
        { id: "5.1", name: "Premium/Discount", description: "Longs in discount (<50%), shorts in premium (>50%).", details: "Calculate from swing low to high.", importance: "high" },
        { id: "5.2", name: "FVG", description: "3-candle imbalance creates FVG.", details: "Gap between C1 high and C3 low (bullish).", importance: "critical" },
    ],
    entry: [
        { id: "6.1", name: "OTE Zone", description: "Entry at 62%-79% retracement.", details: "High-probability Fibonacci zone.", importance: "high" },
        { id: "6.5", name: "ICT 2022 Model", description: "Sweep + displacement + FVG.", details: "Complete entry model sequence.", importance: "critical" },
    ],
    risk: [
        { id: "7.1", name: "Fixed Risk", description: "Risk 1% per trade.", details: "Consistent position sizing.", importance: "critical" },
        { id: "7.2", name: "R:R Minimum", description: "Minimum 1:2 risk-reward.", details: "Ensures profitability at <50% win rate.", importance: "critical" },
    ],
    session: [
        { id: "8.1", name: "Kill Zones", description: "Trade London (2-5 EST) or NY (7-10 EST).", details: "Highest probability windows.", importance: "critical" },
        { id: "8.4", name: "News Rules", description: "No entries 30min around news.", details: "Avoid FOMC, NFP, CPI volatility.", importance: "high" },
    ]
};

const categoryConfig = {
    bias: { label: "Bias", icon: TrendingUp, color: "text-emerald-400" },
    structure: { label: "Structure", icon: Target, color: "text-blue-400" },
    liquidity: { label: "Liquidity", icon: Zap, color: "text-yellow-400" },
    pdArrays: { label: "PD Arrays", icon: Target, color: "text-purple-400" },
    entry: { label: "Entry", icon: Shield, color: "text-orange-400" },
    risk: { label: "Risk", icon: AlertTriangle, color: "text-red-400" },
    session: { label: "Session", icon: Clock, color: "text-cyan-400" }
};

function RuleCard({ rule }: { rule: typeof rulesData.bias[0] }) {
    const [isExpanded, setIsExpanded] = useState(false);
    const colors = { critical: "bg-red-500/20 text-red-400", high: "bg-yellow-500/20 text-yellow-400", medium: "bg-blue-500/20 text-blue-400" };
    return (
        <div className="bg-slate-800/50 rounded-lg overflow-hidden">
            <button onClick={() => setIsExpanded(!isExpanded)} className="w-full flex items-center gap-2 p-3 hover:bg-slate-800 text-left">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                        <Badge variant="outline" className="text-[10px] font-mono">{rule.id}</Badge>
                        <span className="text-sm font-medium text-slate-100">{rule.name}</span>
                        <Badge className={`text-[10px] ${colors[rule.importance as keyof typeof colors]}`}>{rule.importance}</Badge>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">{rule.description}</p>
                </div>
                {isExpanded ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />}
            </button>
            {isExpanded && (
                <div className="px-3 pb-3 pt-0 pl-9">
                    <Separator className="bg-slate-700 mb-2" />
                    <p className="text-xs text-slate-400">{rule.details}</p>
                </div>
            )}
        </div>
    );
}

export default function RulesPage() {
    const { data: health } = useQuery({ queryKey: ["health"], queryFn: getHealth });
    return (
        <div className="flex flex-col h-full w-full overflow-hidden">
            <Header mode={health?.mode || "ANALYSIS_ONLY"} agentAvailable={health?.agent_available || false} />
            <ScrollArea className="flex-1">
                <div className="p-4 min-w-0">
                    <div className="flex items-center gap-3 mb-4">
                        <BookOpen className="w-5 h-5 text-slate-400" />
                        <h2 className="text-lg font-semibold text-slate-100">ICT Trading Rules</h2>
                    </div>
                    <Tabs defaultValue="bias" className="w-full">
                        <TabsList className="bg-slate-800 mb-4 flex flex-wrap h-auto gap-1 p-1">
                            {Object.entries(categoryConfig).map(([key, cfg]) => (
                                <TabsTrigger key={key} value={key} className="text-xs data-[state=active]:bg-slate-700">
                                    <cfg.icon className={`w-3 h-3 mr-1 ${cfg.color}`} />{cfg.label}
                                </TabsTrigger>
                            ))}
                        </TabsList>
                        {Object.entries(rulesData).map(([cat, rules]) => {
                            const cfg = categoryConfig[cat as keyof typeof categoryConfig];
                            return (
                                <TabsContent key={cat} value={cat}>
                                    <Card className="bg-slate-900 border-slate-800">
                                        <CardHeader className="pb-2"><CardTitle className="flex items-center gap-2 text-base"><cfg.icon className={`w-4 h-4 ${cfg.color}`} />{cfg.label}</CardTitle></CardHeader>
                                        <CardContent>
                                            <div className="space-y-2">{rules.map((r) => <RuleCard key={r.id} rule={r} />)}</div>
                                        </CardContent>
                                    </Card>
                                </TabsContent>
                            );
                        })}
                    </Tabs>
                </div>
            </ScrollArea>
        </div>
    );
}
