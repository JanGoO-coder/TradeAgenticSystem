"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Calendar,
    Server,
    Clock,
    TrendingUp,
    Settings2,
    Database,
    Loader2,
} from "lucide-react";
import { MT5StatusPill } from "@/components/dashboard/MT5StatusPill";

interface BacktestStatsBarProps {
    symbol: string;
    fromDate: string;
    toDate: string;
    isLoaded: boolean;
    isLoading?: boolean;
    totalBars: number;
    currentSession?: string;
    onConfigClick: () => void;
    onLoadClick: () => void;
}

export function BacktestStatsBar({
    symbol,
    fromDate,
    toDate,
    isLoaded,
    isLoading = false,
    totalBars,
    currentSession,
    onConfigClick,
    onLoadClick,
}: BacktestStatsBarProps) {
    const formatDate = (dateStr: string) => {
        try {
            return new Date(dateStr).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
            });
        } catch {
            return dateStr;
        }
    };

    return (
        <div className="bg-slate-900 border-b border-slate-800 px-4 py-2">
            <div className="flex items-center justify-between">
                {/* Left: Symbol & Data Info */}
                <div className="flex items-center gap-4">
                    {/* Symbol */}
                    <div className="flex items-center gap-2">
                        <TrendingUp className="w-4 h-4 text-blue-400" />
                        <span className="font-semibold text-slate-100">{symbol}</span>
                    </div>

                    {/* Date Range */}
                    <div className="flex items-center gap-2 text-sm text-slate-400">
                        <Calendar className="w-3.5 h-3.5" />
                        <span>{formatDate(fromDate)}</span>
                        <span>→</span>
                        <span>{formatDate(toDate)}</span>
                    </div>

                    {/* Data Source Badge - Always MT5 */}
                    <Badge
                        variant="outline"
                        className="bg-emerald-500/20 text-emerald-400 border-emerald-500/50"
                    >
                        <Server className="w-3 h-3 mr-1" />
                        MT5 Data
                    </Badge>

                    {/* Bars Count */}
                    {isLoaded && (
                        <Badge variant="outline" className="bg-slate-800 border-slate-700 text-slate-300">
                            <Database className="w-3 h-3 mr-1" />
                            {totalBars} bars
                        </Badge>
                    )}
                </div>

                {/* Right: MT5 Status & Actions */}
                <div className="flex items-center gap-3">
                    {/* Session (if available) */}
                    {currentSession && (
                        <Badge
                            variant="outline"
                            className={
                                currentSession === "London"
                                    ? "bg-blue-500/20 text-blue-400 border-blue-500/50"
                                    : currentSession === "NY"
                                        ? "bg-orange-500/20 text-orange-400 border-orange-500/50"
                                        : "bg-purple-500/20 text-purple-400 border-purple-500/50"
                            }
                        >
                            <Clock className="w-3 h-3 mr-1" />
                            {currentSession}
                        </Badge>
                    )}

                    {/* MT5 Status */}
                    <MT5StatusPill showConnectButton={true} />

                    {/* Config Button */}
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onConfigClick}
                        className="h-7 border-slate-700 text-slate-400 hover:text-slate-100"
                    >
                        <Settings2 className="w-3.5 h-3.5 mr-1" />
                        Config
                    </Button>

                    {/* Load Button */}
                    <Button
                        size="sm"
                        onClick={onLoadClick}
                        disabled={isLoading}
                        className="h-7 bg-blue-600 hover:bg-blue-700"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                                Loading...
                            </>
                        ) : (
                            <>
                                <Database className="w-3.5 h-3.5 mr-1" />
                                {isLoaded ? "Reload" : "Load Data"}
                            </>
                        )}
                    </Button>
                </div>
            </div>
        </div>
    );
}
