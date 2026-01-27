"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
    getSessionPositions,
    getSessionTrades,
    getSessionStatistics,
    closeTrade,
    closeAllSessionPositions,
    HierarchicalPosition,
    HierarchicalClosedTrade,
    CloseReason,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import {
    Activity,
    X,
    Target,
    History,
    BarChart3,
    ArrowUpRight,
    ArrowDownRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface BacktestTradePanelProps {
    className?: string;
    isBacktestLoaded: boolean;
}

export function BacktestTradePanel({ className, isBacktestLoaded }: BacktestTradePanelProps) {
    const queryClient = useQueryClient();
    const [activeTab, setActiveTab] = useState<'positions' | 'history' | 'stats'>('positions');

    // Queries - Using unified session API
    const { data: positionsData } = useQuery({
        queryKey: ['sessionPositions'],
        queryFn: getSessionPositions,
        enabled: isBacktestLoaded,
        refetchInterval: 1000,
    });

    const { data: tradesData } = useQuery({
        queryKey: ['sessionTrades'],
        queryFn: getSessionTrades,
        enabled: isBacktestLoaded,
        refetchInterval: 2000,
    });

    const { data: statistics } = useQuery({
        queryKey: ['sessionStatistics'],
        queryFn: getSessionStatistics,
        enabled: isBacktestLoaded,
        refetchInterval: 2000,
    });

    const positions = positionsData?.positions || [];
    const trades = tradesData?.trades || [];

    // Mutations - Using unified session API
    const closePositionMutation = useMutation({
        mutationFn: ({ positionId, reason }: { positionId: string; reason?: CloseReason }) =>
            closeTrade({ position_id: positionId, reason: reason || 'MANUAL' }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['sessionPositions'] });
            queryClient.invalidateQueries({ queryKey: ['sessionTrades'] });
            queryClient.invalidateQueries({ queryKey: ['sessionStatistics'] });
            queryClient.invalidateQueries({ queryKey: ['sessionState'] });
        },
    });

    const closeAllMutation = useMutation({
        mutationFn: closeAllSessionPositions,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['sessionPositions'] });
            queryClient.invalidateQueries({ queryKey: ['sessionTrades'] });
            queryClient.invalidateQueries({ queryKey: ['sessionStatistics'] });
            queryClient.invalidateQueries({ queryKey: ['sessionState'] });
        },
    });

    // Calculate total unrealized P&L
    const totalUnrealizedPnl = positions.reduce((sum, p) => sum + (p.unrealized_pips || p.unrealized_pnl || 0), 0);

    if (!isBacktestLoaded) {
        return (
            <div className={cn("flex flex-col h-full bg-slate-950 items-center justify-center", className)}>
                <div className="text-slate-500 text-sm text-center p-4">
                    Load backtest data to start trading simulation
                </div>
            </div>
        );
    }

    return (
        <div className={cn("flex flex-col h-full bg-slate-950", className)}>
            {/* Header */}
            <div className="p-3 border-b border-slate-800">
                <div className="flex items-center justify-between mb-2">
                    <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                        <Target className="w-4 h-4" />
                        Backtest Trading
                    </h2>
                    <Badge variant="outline" className="text-xs bg-blue-500/20 text-blue-400 border-blue-500/50">
                        SIMULATION
                    </Badge>
                </div>

                {/* Summary Stats */}
                <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className="bg-slate-900/50 rounded p-2">
                        <div className="text-slate-500">Positions</div>
                        <div className="text-slate-100 font-medium">{positions.length}</div>
                    </div>
                    <div className="bg-slate-900/50 rounded p-2">
                        <div className="text-slate-500">Trades</div>
                        <div className="text-slate-100 font-medium">{trades.length}</div>
                    </div>
                    <div className="bg-slate-900/50 rounded p-2">
                        <div className="text-slate-500">Unrealized</div>
                        <div className={cn(
                            "font-medium",
                            totalUnrealizedPnl >= 0 ? "text-emerald-400" : "text-red-400"
                        )}>
                            {totalUnrealizedPnl >= 0 ? '+' : ''}{totalUnrealizedPnl.toFixed(1)} pips
                        </div>
                    </div>
                </div>
            </div>

            {/* Tab Navigation */}
            <div className="flex gap-1 p-2 border-b border-slate-800">
                <Button
                    variant={activeTab === 'positions' ? 'secondary' : 'ghost'}
                    size="sm"
                    className="h-7 text-xs flex-1"
                    onClick={() => setActiveTab('positions')}
                >
                    <Activity className="w-3 h-3 mr-1" />
                    Open ({positions.length})
                </Button>
                <Button
                    variant={activeTab === 'history' ? 'secondary' : 'ghost'}
                    size="sm"
                    className="h-7 text-xs flex-1"
                    onClick={() => setActiveTab('history')}
                >
                    <History className="w-3 h-3 mr-1" />
                    History ({trades.length})
                </Button>
                <Button
                    variant={activeTab === 'stats' ? 'secondary' : 'ghost'}
                    size="sm"
                    className="h-7 text-xs flex-1"
                    onClick={() => setActiveTab('stats')}
                >
                    <BarChart3 className="w-3 h-3 mr-1" />
                    Stats
                </Button>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto">
                {/* Positions Tab */}
                {activeTab === 'positions' && (
                    <div className="p-2">
                        {positions.length === 0 ? (
                            <div className="text-center text-slate-500 text-xs py-8">
                                No open positions
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {positions.map((position) => (
                                    <BacktestPositionCard
                                        key={position.id}
                                        position={position}
                                        onClose={(id) => closePositionMutation.mutate({ positionId: id })}
                                        isClosing={closePositionMutation.isPending}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* History Tab */}
                {activeTab === 'history' && (
                    <div className="p-2">
                        {trades.length === 0 ? (
                            <div className="text-center text-slate-500 text-xs py-8">
                                No completed trades
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {[...trades].reverse().map((trade) => (
                                    <BacktestTradeCard key={trade.id} trade={trade} />
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Stats Tab */}
                {activeTab === 'stats' && statistics && (
                    <div className="p-3 space-y-3">
                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardHeader className="p-3 pb-2">
                                <CardTitle className="text-xs text-slate-400">Performance</CardTitle>
                            </CardHeader>
                            <CardContent className="p-3 pt-0 space-y-2 text-xs">
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Total Trades</span>
                                    <span className="text-slate-100">{statistics.total_trades}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Win Rate</span>
                                    <span className={statistics.win_rate >= 0.5 ? "text-emerald-400" : "text-red-400"}>
                                        {(statistics.win_rate * 100).toFixed(1)}%
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Profit Factor</span>
                                    <span className={statistics.profit_factor >= 1 ? "text-emerald-400" : "text-red-400"}>
                                        {statistics.profit_factor === Infinity ? '∞' : statistics.profit_factor.toFixed(2)}
                                    </span>
                                </div>
                                <Separator className="bg-slate-800" />
                                <div className="flex justify-between font-medium">
                                    <span className="text-slate-400">Total P&L</span>
                                    <span className={statistics.total_pnl_pips >= 0 ? "text-emerald-400" : "text-red-400"}>
                                        {statistics.total_pnl_pips >= 0 ? '+' : ''}{statistics.total_pnl_pips.toFixed(1)} pips
                                    </span>
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardHeader className="p-3 pb-2">
                                <CardTitle className="text-xs text-slate-400">Breakdown</CardTitle>
                            </CardHeader>
                            <CardContent className="p-3 pt-0 space-y-2 text-xs">
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Winners</span>
                                    <span className="text-emerald-400">{statistics.winners}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Losers</span>
                                    <span className="text-red-400">{statistics.losers}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Avg Win</span>
                                    <span className="text-emerald-400">+{statistics.average_win_pips.toFixed(1)} pips</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Avg Loss</span>
                                    <span className="text-red-400">-{statistics.average_loss_pips.toFixed(1)} pips</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Avg R:R</span>
                                    <span className="text-slate-100">{statistics.average_rr.toFixed(2)}R</span>
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardHeader className="p-3 pb-2">
                                <CardTitle className="text-xs text-slate-400">Risk Metrics</CardTitle>
                            </CardHeader>
                            <CardContent className="p-3 pt-0 space-y-2 text-xs">
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Max Drawdown</span>
                                    <span className="text-red-400">-{statistics.max_drawdown_pips.toFixed(1)} pips</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Largest Win</span>
                                    <span className="text-emerald-400">+{statistics.largest_win_pips.toFixed(1)} pips</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Largest Loss</span>
                                    <span className="text-red-400">{statistics.largest_loss_pips.toFixed(1)} pips</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Max Consec. Wins</span>
                                    <span className="text-slate-100">{statistics.consecutive_wins}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Max Consec. Losses</span>
                                    <span className="text-slate-100">{statistics.consecutive_losses}</span>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                )}
            </div>

            {/* Actions Footer */}
            {positions.length > 0 && (
                <div className="p-2 border-t border-slate-800">
                    <AlertDialog>
                        <AlertDialogTrigger asChild>
                            <Button
                                variant="outline"
                                size="sm"
                                className="w-full h-8 border-red-500/50 text-red-400 hover:bg-red-500/10"
                            >
                                <X className="w-3 h-3 mr-1" />
                                Close All ({positions.length})
                            </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent className="bg-slate-900 border-slate-800">
                            <AlertDialogHeader>
                                <AlertDialogTitle className="text-slate-100">Close All Positions</AlertDialogTitle>
                                <AlertDialogDescription className="text-slate-400">
                                    This will close all {positions.length} open backtest positions at the current price.
                                </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                                <AlertDialogCancel className="border-slate-700">Cancel</AlertDialogCancel>
                                <AlertDialogAction
                                    className="bg-red-600 hover:bg-red-700"
                                    onClick={() => closeAllMutation.mutate()}
                                >
                                    Close All
                                </AlertDialogAction>
                            </AlertDialogFooter>
                        </AlertDialogContent>
                    </AlertDialog>
                </div>
            )}
        </div>
    );
}

// Position Card Component - Using unified HierarchicalPosition type
function BacktestPositionCard({
    position,
    onClose,
    isClosing
}: {
    position: HierarchicalPosition;
    onClose: (id: string) => void;
    isClosing: boolean;
}) {
    const isLong = position.direction === 'LONG';
    const pnl = position.unrealized_pips || position.unrealized_pnl || 0;

    return (
        <Card className="bg-slate-900/50 border-slate-800">
            <CardContent className="p-2">
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        <Badge
                            variant="outline"
                            className={cn(
                                "text-xs px-1.5",
                                isLong
                                    ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50"
                                    : "bg-red-500/20 text-red-400 border-red-500/50"
                            )}
                        >
                            {isLong ? <ArrowUpRight className="w-3 h-3 mr-0.5" /> : <ArrowDownRight className="w-3 h-3 mr-0.5" />}
                            {position.direction}
                        </Badge>
                        <span className="text-xs text-slate-400">{position.volume} lot</span>
                    </div>
                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-6 w-6 p-0 text-slate-400 hover:text-red-400"
                                    onClick={() => onClose(position.id)}
                                    disabled={isClosing}
                                >
                                    <X className="w-3 h-3" />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent side="left">Close Position</TooltipContent>
                        </Tooltip>
                    </TooltipProvider>
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs">
                    <div>
                        <div className="text-slate-500">Entry</div>
                        <div className="text-slate-100">{position.entry_price.toFixed(5)}</div>
                    </div>
                    <div>
                        <div className="text-slate-500">SL</div>
                        <div className="text-red-400">{position.stop_loss.toFixed(5)}</div>
                    </div>
                    <div>
                        <div className="text-slate-500">TP</div>
                        <div className="text-emerald-400">
                            {position.take_profit ? position.take_profit.toFixed(5) : '-'}
                        </div>
                    </div>
                </div>

                {/* Show current price if available (backtest mode) */}
                {position.current_price && (
                    <div className="flex justify-between items-center mt-2 text-xs">
                        <span className="text-slate-500">Current</span>
                        <span className="text-slate-100">{position.current_price.toFixed(5)}</span>
                    </div>
                )}

                <div className="flex justify-between items-center mt-2 pt-2 border-t border-slate-800">
                    <span className="text-xs text-slate-500">P&L</span>
                    <span className={cn(
                        "text-xs font-medium",
                        pnl >= 0 ? "text-emerald-400" : "text-red-400"
                    )}>
                        {pnl >= 0 ? '+' : ''}{pnl.toFixed(1)} pips
                    </span>
                </div>

                {position.setup_name && (
                    <Badge variant="outline" className="mt-2 text-xs bg-blue-500/10 text-blue-400 border-blue-500/30">
                        {position.setup_name}
                    </Badge>
                )}
            </CardContent>
        </Card>
    );
}

// Trade History Card Component - Using unified HierarchicalClosedTrade type
function BacktestTradeCard({ trade }: { trade: HierarchicalClosedTrade }) {
    const isLong = trade.direction === 'LONG';
    const isWin = trade.pnl_pips > 0;

    const getExitReasonBadge = (reason: string) => {
        switch (reason) {
            case 'TP_HIT':
                return <Badge variant="outline" className="text-xs bg-emerald-500/20 text-emerald-400 border-emerald-500/50">TP</Badge>;
            case 'SL_HIT':
                return <Badge variant="outline" className="text-xs bg-red-500/20 text-red-400 border-red-500/50">SL</Badge>;
            case 'MANUAL':
                return <Badge variant="outline" className="text-xs bg-slate-500/20 text-slate-400 border-slate-500/50">Manual</Badge>;
            default:
                return <Badge variant="outline" className="text-xs bg-slate-500/20 text-slate-400 border-slate-500/50">{reason}</Badge>;
        }
    };

    return (
        <Card className={cn(
            "border-l-2",
            isWin ? "border-l-emerald-500 bg-emerald-500/5" : "border-l-red-500 bg-red-500/5",
            "bg-slate-900/50 border-slate-800"
        )}>
            <CardContent className="p-2">
                <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                        <Badge
                            variant="outline"
                            className={cn(
                                "text-xs px-1.5",
                                isLong
                                    ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50"
                                    : "bg-red-500/20 text-red-400 border-red-500/50"
                            )}
                        >
                            {isLong ? <ArrowUpRight className="w-3 h-3 mr-0.5" /> : <ArrowDownRight className="w-3 h-3 mr-0.5" />}
                            {trade.direction}
                        </Badge>
                        {getExitReasonBadge(trade.close_reason)}
                    </div>
                    <span className={cn(
                        "text-xs font-semibold",
                        isWin ? "text-emerald-400" : "text-red-400"
                    )}>
                        {trade.pnl_pips >= 0 ? '+' : ''}{trade.pnl_pips.toFixed(1)} pips ({trade.pnl_rr.toFixed(2)}R)
                    </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                        <div className="text-slate-500">Entry</div>
                        <div className="text-slate-100">{trade.entry_price.toFixed(5)}</div>
                    </div>
                    <div>
                        <div className="text-slate-500">Exit</div>
                        <div className="text-slate-100">{trade.exit_price.toFixed(5)}</div>
                    </div>
                </div>

                <div className="flex items-center justify-between mt-1 text-xs text-slate-500">
                    <span>Spread: {(trade.spread_at_entry || 0) * 10000 > 0 ? ((trade.spread_at_entry || 0) * 10000).toFixed(1) : '-'} pips</span>
                    <span>{(trade.closed_at || trade.exit_timestamp || '').slice(0, 16).replace('T', ' ')}</span>
                </div>

                {trade.setup_name && (
                    <Badge variant="outline" className="mt-2 text-xs bg-blue-500/10 text-blue-400 border-blue-500/30">
                        {trade.setup_name}
                    </Badge>
                )}
            </CardContent>
        </Card>
    );
}
