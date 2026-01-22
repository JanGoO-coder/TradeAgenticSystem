"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface BiasCardProps {
    bias: "BULLISH" | "BEARISH" | "NEUTRAL";
    ruleRefs: string[];
    timeframe: string;
}

export function BiasCard({ bias, ruleRefs, timeframe }: BiasCardProps) {
    const getBiasConfig = (bias: string) => {
        switch (bias) {
            case "BULLISH":
                return {
                    icon: TrendingUp,
                    color: "text-emerald-400",
                    bgColor: "bg-emerald-500/10",
                    borderColor: "border-emerald-500/30",
                };
            case "BEARISH":
                return {
                    icon: TrendingDown,
                    color: "text-red-400",
                    bgColor: "bg-red-500/10",
                    borderColor: "border-red-500/30",
                };
            default:
                return {
                    icon: Minus,
                    color: "text-slate-400",
                    bgColor: "bg-slate-500/10",
                    borderColor: "border-slate-500/30",
                };
        }
    };

    const config = getBiasConfig(bias);
    const Icon = config.icon;

    return (
        <Card className={`bg-slate-900 border-slate-800 ${config.bgColor}`}>
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-slate-400 flex items-center justify-between">
                    <span>{timeframe} Bias</span>
                    <Badge variant="outline" className="text-xs text-slate-500 border-slate-700">
                        {ruleRefs.join(", ")}
                    </Badge>
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="flex items-center gap-3">
                    <div className={`p-3 rounded-lg ${config.bgColor} ${config.borderColor} border`}>
                        <Icon className={`w-8 h-8 ${config.color}`} />
                    </div>
                    <div>
                        <div className={`text-2xl font-bold ${config.color}`}>{bias}</div>
                        <div className="text-xs text-slate-500">Market Structure</div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
