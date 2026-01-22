"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { TradeSetupResponse } from "@/lib/api";
import {
    Target,
    TrendingUp,
    TrendingDown,
    AlertCircle,
    CheckCircle2,
    XCircle,
    ChevronRight
} from "lucide-react";

interface TradeSetupViewerProps {
    setup: TradeSetupResponse | null;
    onClose?: () => void;
}

export function TradeSetupViewer({ setup, onClose }: TradeSetupViewerProps) {
    if (!setup) {
        return (
            <Card className="bg-slate-900 border-slate-800">
                <CardContent className="py-12 text-center">
                    <Target className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <p className="text-slate-500">No setup to display</p>
                    <p className="text-xs text-slate-600 mt-1">Run analysis to see trade details</p>
                </CardContent>
            </Card>
        );
    }

    const isLong = setup.htf_bias.value === "BULLISH";
    const statusColors = {
        TRADE_NOW: "bg-emerald-500",
        WAIT: "bg-yellow-500",
        NO_TRADE: "bg-slate-500",
    };

    return (
        <Card className="bg-slate-900 border-slate-800">
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${isLong ? "bg-emerald-500/10" : "bg-red-500/10"}`}>
                            {isLong ? (
                                <TrendingUp className="w-6 h-6 text-emerald-400" />
                            ) : (
                                <TrendingDown className="w-6 h-6 text-red-400" />
                            )}
                        </div>
                        <div>
                            <CardTitle className="text-lg">{setup.setup.name}</CardTitle>
                            <div className="flex items-center gap-2 mt-1">
                                <Badge variant="outline" className="text-xs">
                                    {setup.symbol}
                                </Badge>
                                <Badge variant="outline" className="text-xs">
                                    {setup.setup.type}
                                </Badge>
                            </div>
                        </div>
                    </div>
                    <Badge className={`${statusColors[setup.status]}/20 text-white`}>
                        {setup.status.replace("_", " ")}
                    </Badge>
                </div>
            </CardHeader>

            <CardContent>
                <Tabs defaultValue="levels" className="w-full">
                    <TabsList className="grid w-full grid-cols-3 bg-slate-800">
                        <TabsTrigger value="levels">Price Levels</TabsTrigger>
                        <TabsTrigger value="risk">Risk</TabsTrigger>
                        <TabsTrigger value="rules">Rules Used</TabsTrigger>
                    </TabsList>

                    <TabsContent value="levels" className="mt-4">
                        <div className="space-y-3">
                            {/* Entry */}
                            <div className="flex justify-between items-center p-3 bg-slate-800/50 rounded-lg">
                                <div className="flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-blue-400" />
                                    <span className="text-sm text-slate-400">Entry Price</span>
                                </div>
                                <span className="font-mono text-slate-100">
                                    {setup.setup.entry_price?.toFixed(5) || "—"}
                                </span>
                            </div>

                            {/* Stop Loss */}
                            <div className="flex justify-between items-center p-3 bg-slate-800/50 rounded-lg">
                                <div className="flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-red-400" />
                                    <span className="text-sm text-slate-400">Stop Loss</span>
                                </div>
                                <span className="font-mono text-red-400">
                                    {setup.setup.stop_loss?.toFixed(5) || "—"}
                                </span>
                            </div>

                            {/* Take Profits */}
                            {setup.setup.take_profit?.map((tp, i) => (
                                <div key={i} className="flex justify-between items-center p-3 bg-slate-800/50 rounded-lg">
                                    <div className="flex items-center gap-2">
                                        <div className="w-2 h-2 rounded-full bg-emerald-400" />
                                        <span className="text-sm text-slate-400">TP {i + 1}</span>
                                    </div>
                                    <span className="font-mono text-emerald-400">
                                        {tp.toFixed(5)}
                                    </span>
                                </div>
                            ))}

                            {/* Invalidation */}
                            <div className="flex justify-between items-center p-3 bg-slate-800/50 rounded-lg border border-orange-500/30">
                                <div className="flex items-center gap-2">
                                    <AlertCircle className="w-4 h-4 text-orange-400" />
                                    <span className="text-sm text-slate-400">Invalidation</span>
                                </div>
                                <span className="font-mono text-orange-400">
                                    {setup.setup.invalidation_point?.toFixed(5) || "—"}
                                </span>
                            </div>
                        </div>
                    </TabsContent>

                    <TabsContent value="risk" className="mt-4">
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="bg-slate-800/50 rounded-lg p-4">
                                    <div className="text-sm text-slate-400 mb-1">Account Balance</div>
                                    <div className="text-xl font-semibold text-slate-100">
                                        ${setup.risk.account_balance.toLocaleString()}
                                    </div>
                                </div>
                                <div className="bg-slate-800/50 rounded-lg p-4">
                                    <div className="text-sm text-slate-400 mb-1">Risk Amount</div>
                                    <div className="text-xl font-semibold text-red-400">
                                        ${(setup.risk.account_balance * setup.risk.risk_pct / 100).toFixed(2)}
                                    </div>
                                </div>
                            </div>

                            <div className="grid grid-cols-3 gap-4">
                                <div className="bg-slate-800/50 rounded-lg p-4 text-center">
                                    <div className="text-2xl font-bold text-slate-100">{setup.risk.risk_pct}%</div>
                                    <div className="text-xs text-slate-500">Risk Per Trade</div>
                                </div>
                                <div className="bg-slate-800/50 rounded-lg p-4 text-center">
                                    <div className="text-2xl font-bold text-emerald-400">{setup.risk.position_size}</div>
                                    <div className="text-xs text-slate-500">Lot Size</div>
                                </div>
                                <div className="bg-slate-800/50 rounded-lg p-4 text-center">
                                    <div className="text-2xl font-bold text-blue-400">1:{setup.risk.rr?.toFixed(1)}</div>
                                    <div className="text-xs text-slate-500">R:R Ratio</div>
                                </div>
                            </div>
                        </div>
                    </TabsContent>

                    <TabsContent value="rules" className="mt-4">
                        <ScrollArea className="h-[200px]">
                            <div className="space-y-2">
                                {setup.setup.rule_refs.map((rule) => (
                                    <div key={rule} className="flex items-center gap-2 p-2 bg-slate-800/50 rounded">
                                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                                        <span className="text-sm text-slate-300">Rule {rule}</span>
                                        <ChevronRight className="w-4 h-4 text-slate-600 ml-auto" />
                                    </div>
                                ))}
                            </div>
                        </ScrollArea>
                    </TabsContent>
                </Tabs>
            </CardContent>
        </Card>
    );
}
