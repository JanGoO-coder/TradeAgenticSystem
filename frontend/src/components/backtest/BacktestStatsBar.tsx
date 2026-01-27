"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Calendar,
    Server,
    Clock,
    TrendingUp,
    TrendingDown,
    Settings2,
    Database,
    Loader2,
    Download,
    Target,
    Percent,
} from "lucide-react";
import { MT5StatusPill } from "@/components/dashboard/MT5StatusPill";
import { BacktestStatistics } from "@/lib/api";

interface BacktestStatsBarProps {
    symbol: string;
    fromDate: string;
    toDate: string;
    dataSource: "mt5" | "sample";
    isLoaded: boolean;
    isLoading?: boolean;
    totalBars: number;
    currentSession?: string;
    statistics?: BacktestStatistics | null;
    onConfigClick: () => void;
    onLoadClick: () => void;
    onExportClick?: () => void;
    isExporting?: boolean;
}

export function BacktestStatsBar({
    symbol,
    fromDate,
    toDate,
    dataSource,
    isLoaded,
    isLoading = false,
    totalBars,
    currentSession,
    statistics,
    onConfigClick,
    onLoadClick,
    onExportClick,
    isExporting = false,
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

                    {/* Data Source Badge */}
                    <Badge
                        variant="outline"
                        className={dataSource === "mt5"
                            ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50"
                            : "bg-slate-500/20 text-slate-400 border-slate-500/50"
                        }
                    >
                        <Server className="w-3 h-3 mr-1" />
                        {dataSource === "mt5" ? "MT5 Data" : "Sample Data"}
                    </Badge>

                    {/* Bars Count */}
                    {isLoaded && (
                        <Badge variant="outline" className="bg-slate-800 border-slate-700 text-slate-300">
                            <Database className="w-3 h-3 mr-1" />
                            {totalBars} bars
                        </Badge>
                    )}

                    {/* Backtest Statistics */}
                    {statistics && statistics.total_trades > 0 && (
                        <>
                            <div className="h-4 w-px bg-slate-700" />

                            {/* Trades Count */}
                            <Badge variant="outline" className="bg-slate-800 border-slate-700 text-slate-300">
                                <Target className="w-3 h-3 mr-1" />
                                {statistics.total_trades} trades
                            </Badge>

                            {/* Win Rate */}
                            <Badge
                                variant="outline"
                                className={statistics.win_rate >= 0.5
                                    ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50"
                                    : "bg-red-500/20 text-red-400 border-red-500/50"
                                }
                            >
                                <Percent className="w-3 h-3 mr-1" />
                                {(statistics.win_rate * 100).toFixed(1)}% WR
                            </Badge>

                            {/* Total P&L */}
                            <Badge
                                variant="outline"
                                className={statistics.total_pnl_pips >= 0
                                    ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50"
                                    : "bg-red-500/20 text-red-400 border-red-500/50"
                                }
                            >
                                {statistics.total_pnl_pips >= 0 ? (
                                    <TrendingUp className="w-3 h-3 mr-1" />
                                ) : (
                                    <TrendingDown className="w-3 h-3 mr-1" />
                                )}
                                {statistics.total_pnl_pips >= 0 ? "+" : ""}{statistics.total_pnl_pips.toFixed(1)} pips
                            </Badge>

                            {/* Profit Factor */}
                            {statistics.profit_factor > 0 && statistics.profit_factor !== Infinity && (
                                <Badge variant="outline" className="bg-slate-800 border-slate-700 text-slate-300">
                                    PF: {statistics.profit_factor.toFixed(2)}
                                </Badge>
                            )}
                        </>
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

                    {/* Export Button */}
                    {isLoaded && statistics && statistics.total_trades > 0 && onExportClick && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={onExportClick}
                            disabled={isExporting}
                            className="h-7 border-slate-700 text-slate-400 hover:text-slate-100"
                        >
                            {isExporting ? (
                                <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                            ) : (
                                <Download className="w-3.5 h-3.5 mr-1" />
                            )}
                            Export
                        </Button>
                    )}
                </div>
            </div>
        </div>
    );
}
