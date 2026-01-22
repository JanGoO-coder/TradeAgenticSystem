"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowRight, Target, StopCircle, TrendingUp, CheckCircle2 } from "lucide-react";
import { TradeSetupResponse } from "@/lib/api";

interface SetupCardProps {
    setup: TradeSetupResponse | null;
}

export function SetupCard({ setup }: SetupCardProps) {
    if (!setup) {
        return (
            <Card className="bg-slate-900 border-slate-800">
                <CardHeader>
                    <CardTitle className="text-sm font-medium text-slate-400">
                        Active Setup
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="text-center py-8 text-slate-500">
                        <Target className="w-12 h-12 mx-auto mb-3 opacity-50" />
                        <p>No active setup</p>
                        <p className="text-xs mt-1">Run analysis to detect setups</p>
                    </div>
                </CardContent>
            </Card>
        );
    }

    const getStatusConfig = (status: string) => {
        switch (status) {
            case "TRADE_NOW":
                return { color: "bg-emerald-500", text: "text-emerald-400", label: "Trade Now" };
            case "WAIT":
                return { color: "bg-yellow-500", text: "text-yellow-400", label: "Wait" };
            default:
                return { color: "bg-slate-500", text: "text-slate-400", label: "No Trade" };
        }
    };

    const statusConfig = getStatusConfig(setup.status);

    return (
        <Card className="bg-slate-900 border-slate-800">
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium text-slate-400">
                        Active Setup
                    </CardTitle>
                    <Badge className={`${statusConfig.color}/20 ${statusConfig.text}`}>
                        {statusConfig.label}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent>
                <div className="space-y-4">
                    {/* Setup Name & Symbol */}
                    <div>
                        <div className="text-lg font-semibold text-slate-100">
                            {setup.setup.name || "No Setup"}
                        </div>
                        <div className="text-sm text-slate-400">
                            {setup.symbol} • {setup.setup.type}
                        </div>
                    </div>

                    {/* Price Levels */}
                    {setup.setup.entry_price && (
                        <div className="grid grid-cols-3 gap-2 text-sm">
                            <div className="bg-slate-800 rounded-lg p-2">
                                <div className="text-slate-500 text-xs">Entry</div>
                                <div className="text-slate-100 font-mono">
                                    {setup.setup.entry_price.toFixed(5)}
                                </div>
                            </div>
                            <div className="bg-slate-800 rounded-lg p-2">
                                <div className="text-slate-500 text-xs">Stop Loss</div>
                                <div className="text-red-400 font-mono">
                                    {setup.setup.stop_loss?.toFixed(5) || "-"}
                                </div>
                            </div>
                            <div className="bg-slate-800 rounded-lg p-2">
                                <div className="text-slate-500 text-xs">Take Profit</div>
                                <div className="text-emerald-400 font-mono">
                                    {setup.setup.take_profit?.[0]?.toFixed(5) || "-"}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Confluence & Confidence */}
                    <div className="flex items-center justify-between">
                        <div>
                            <span className="text-slate-500 text-sm">Confluence:</span>
                            <span className="ml-2 text-slate-100 font-semibold">
                                {setup.setup.confluence_score}/10
                            </span>
                        </div>
                        <div>
                            <span className="text-slate-500 text-sm">R:R:</span>
                            <span className="ml-2 text-emerald-400 font-semibold">
                                1:{setup.risk.rr?.toFixed(1) || "-"}
                            </span>
                        </div>
                    </div>

                    {/* Reason */}
                    <div className="text-xs text-slate-500 bg-slate-800/50 rounded p-2">
                        {setup.reason_short}
                    </div>

                    {/* Action Buttons */}
                    {setup.status === "TRADE_NOW" && (
                        <div className="flex gap-2">
                            <Button className="flex-1 bg-emerald-600 hover:bg-emerald-700">
                                <CheckCircle2 className="w-4 h-4 mr-2" />
                                Approve
                            </Button>
                            <Button variant="outline" className="border-slate-700 text-slate-400">
                                Reject
                            </Button>
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
