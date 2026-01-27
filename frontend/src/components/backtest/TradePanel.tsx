"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
    getAccountInfo,
    getPositions,
    getPendingOrders,
    getRiskLimits,
    getDailyStats,
    closePosition,
    closeAllPositions,
    cancelOrder,
    modifyPosition,
    triggerEmergencyStop,
    getMode,
    AccountInfo,
    Position,
    PendingOrder,
    RiskLimits,
    DailyStats,
    OrderRequest,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
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
    AlertTriangle,
    TrendingUp,
    TrendingDown,
    DollarSign,
    Activity,
    Shield,
    Ban,
    Edit2,
    X,
    RefreshCw,
    Wallet,
    BarChart3,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface TradePanelProps {
    className?: string;
    onExecuteTrade?: (order: Partial<OrderRequest>) => void;
    currentSetup?: {
        symbol: string;
        direction: 'LONG' | 'SHORT';
        entry_price: number;
        stop_loss: number;
        take_profit?: number;
    } | null;
}

export function TradePanel({ className, onExecuteTrade, currentSetup }: TradePanelProps) {
    const queryClient = useQueryClient();
    const [activeTab, setActiveTab] = useState<'positions' | 'orders' | 'stats'>('positions');

    // Queries
    const { data: account, isLoading: accountLoading } = useQuery({
        queryKey: ['accountInfo'],
        queryFn: getAccountInfo,
        refetchInterval: 5000,
        retry: false,
    });

    const { data: positions = [], isLoading: positionsLoading } = useQuery({
        queryKey: ['positions'],
        queryFn: () => getPositions(),
        refetchInterval: 2000,
    });

    const { data: orders = [], isLoading: ordersLoading } = useQuery({
        queryKey: ['pendingOrders'],
        queryFn: () => getPendingOrders(),
        refetchInterval: 5000,
    });

    const { data: riskLimits } = useQuery({
        queryKey: ['riskLimits'],
        queryFn: getRiskLimits,
        refetchInterval: 10000,
    });

    const { data: dailyStats } = useQuery({
        queryKey: ['dailyStats'],
        queryFn: getDailyStats,
        refetchInterval: 10000,
    });

    const { data: mode } = useQuery({
        queryKey: ['mode'],
        queryFn: getMode,
        refetchInterval: 5000,
    });

    // Mutations
    const closePositionMutation = useMutation({
        mutationFn: ({ ticket, volume }: { ticket: number; volume?: number }) =>
            closePosition(ticket, volume),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['positions'] });
            queryClient.invalidateQueries({ queryKey: ['accountInfo'] });
            queryClient.invalidateQueries({ queryKey: ['dailyStats'] });
        },
    });

    const closeAllMutation = useMutation({
        mutationFn: closeAllPositions,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['positions'] });
            queryClient.invalidateQueries({ queryKey: ['accountInfo'] });
            queryClient.invalidateQueries({ queryKey: ['dailyStats'] });
        },
    });

    const cancelOrderMutation = useMutation({
        mutationFn: cancelOrder,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['pendingOrders'] });
        },
    });

    const emergencyStopMutation = useMutation({
        mutationFn: () => triggerEmergencyStop({
            close_all_positions: true,
            cancel_pending_orders: true,
            reason: "Emergency stop triggered from UI"
        }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['positions'] });
            queryClient.invalidateQueries({ queryKey: ['pendingOrders'] });
            queryClient.invalidateQueries({ queryKey: ['accountInfo'] });
        },
    });

    // Calculate total P&L
    const totalFloatingPnl = positions.reduce((sum, p) => sum + p.profit, 0);

    // Determine execution mode badge color
    const getModeColor = (mode: string) => {
        switch (mode) {
            case 'EXECUTION': return 'bg-red-500/20 text-red-400 border-red-500/50';
            case 'SIMULATION': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50';
            case 'APPROVAL_REQUIRED': return 'bg-orange-500/20 text-orange-400 border-orange-500/50';
            default: return 'bg-slate-500/20 text-slate-400 border-slate-500/50';
        }
    };

    return (
        <div className={cn("flex flex-col h-full bg-slate-950", className)}>
            {/* Header with Account Summary */}
            <div className="p-3 border-b border-slate-800">
                <div className="flex items-center justify-between mb-2">
                    <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                        <Wallet className="w-4 h-4" />
                        Trading Panel
                    </h2>
                    <Badge variant="outline" className={cn("text-xs", getModeColor(mode?.mode || 'ANALYSIS_ONLY'))}>
                        {mode?.mode || 'ANALYSIS_ONLY'}
                    </Badge>
                </div>

                {/* Account Summary */}
                {account && (
                    <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="bg-slate-900/50 rounded p-2">
                            <div className="text-slate-500">Balance</div>
                            <div className="text-slate-100 font-medium">
                                ${account.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </div>
                        </div>
                        <div className="bg-slate-900/50 rounded p-2">
                            <div className="text-slate-500">Equity</div>
                            <div className="text-slate-100 font-medium">
                                ${account.equity.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </div>
                        </div>
                        <div className="bg-slate-900/50 rounded p-2">
                            <div className="text-slate-500">Floating P&L</div>
                            <div className={cn(
                                "font-medium",
                                totalFloatingPnl >= 0 ? "text-emerald-400" : "text-red-400"
                            )}>
                                {totalFloatingPnl >= 0 ? '+' : ''}${totalFloatingPnl.toFixed(2)}
                            </div>
                        </div>
                        <div className="bg-slate-900/50 rounded p-2">
                            <div className="text-slate-500">Margin Level</div>
                            <div className={cn(
                                "font-medium",
                                (account.margin_level || 0) > 200 ? "text-emerald-400" :
                                (account.margin_level || 0) > 100 ? "text-yellow-400" : "text-red-400"
                            )}>
                                {account.margin_level ? `${account.margin_level.toFixed(0)}%` : 'N/A'}
                            </div>
                        </div>
                    </div>
                )}

                {!account && !accountLoading && (
                    <div className="text-xs text-slate-500 bg-slate-900/50 rounded p-2 text-center">
                        MT5 not connected
                    </div>
                )}
            </div>

            {/* Risk Limits Warning */}
            {riskLimits && !riskLimits.can_trade && (
                <div className="mx-3 mt-2 p-2 bg-red-500/10 border border-red-500/30 rounded text-xs text-red-400 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>{riskLimits.block_reason}</span>
                </div>
            )}

            {/* Tab Navigation */}
            <div className="flex gap-1 p-2 border-b border-slate-800">
                <Button
                    variant={activeTab === 'positions' ? 'secondary' : 'ghost'}
                    size="sm"
                    className="h-7 text-xs flex-1"
                    onClick={() => setActiveTab('positions')}
                >
                    <Activity className="w-3 h-3 mr-1" />
                    Positions ({positions.length})
                </Button>
                <Button
                    variant={activeTab === 'orders' ? 'secondary' : 'ghost'}
                    size="sm"
                    className="h-7 text-xs flex-1"
                    onClick={() => setActiveTab('orders')}
                >
                    <BarChart3 className="w-3 h-3 mr-1" />
                    Orders ({orders.length})
                </Button>
                <Button
                    variant={activeTab === 'stats' ? 'secondary' : 'ghost'}
                    size="sm"
                    className="h-7 text-xs flex-1"
                    onClick={() => setActiveTab('stats')}
                >
                    <DollarSign className="w-3 h-3 mr-1" />
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
                                    <PositionCard
                                        key={position.ticket}
                                        position={position}
                                        onClose={(ticket, volume) => closePositionMutation.mutate({ ticket, volume })}
                                        isClosing={closePositionMutation.isPending}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Orders Tab */}
                {activeTab === 'orders' && (
                    <div className="p-2">
                        {orders.length === 0 ? (
                            <div className="text-center text-slate-500 text-xs py-8">
                                No pending orders
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {orders.map((order) => (
                                    <OrderCard
                                        key={order.ticket}
                                        order={order}
                                        onCancel={(ticket) => cancelOrderMutation.mutate(ticket)}
                                        isCancelling={cancelOrderMutation.isPending}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Stats Tab */}
                {activeTab === 'stats' && dailyStats && riskLimits && (
                    <div className="p-3 space-y-3">
                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardHeader className="p-3 pb-2">
                                <CardTitle className="text-xs text-slate-400">Today's Stats</CardTitle>
                            </CardHeader>
                            <CardContent className="p-3 pt-0 space-y-2 text-xs">
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Trades</span>
                                    <span className="text-slate-100">{dailyStats.trades_count} / {riskLimits.max_trades_per_day}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Realized P&L</span>
                                    <span className={dailyStats.realized_pnl >= 0 ? "text-emerald-400" : "text-red-400"}>
                                        {dailyStats.realized_pnl >= 0 ? '+' : ''}${dailyStats.realized_pnl.toFixed(2)}
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Floating P&L</span>
                                    <span className={dailyStats.floating_pnl >= 0 ? "text-emerald-400" : "text-red-400"}>
                                        {dailyStats.floating_pnl >= 0 ? '+' : ''}${dailyStats.floating_pnl.toFixed(2)}
                                    </span>
                                </div>
                                <Separator className="bg-slate-800" />
                                <div className="flex justify-between font-medium">
                                    <span className="text-slate-400">Total P&L</span>
                                    <span className={dailyStats.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"}>
                                        {dailyStats.total_pnl >= 0 ? '+' : ''}${dailyStats.total_pnl.toFixed(2)}
                                    </span>
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardHeader className="p-3 pb-2">
                                <CardTitle className="text-xs text-slate-400">Risk Usage</CardTitle>
                            </CardHeader>
                            <CardContent className="p-3 pt-0 space-y-2 text-xs">
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Open Positions</span>
                                    <span className="text-slate-100">
                                        {riskLimits.current_open_positions} / {riskLimits.max_open_positions}
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Daily Loss</span>
                                    <span className={riskLimits.current_daily_loss_pct > 3 ? "text-red-400" : "text-slate-100"}>
                                        {riskLimits.current_daily_loss_pct.toFixed(2)}% / {riskLimits.max_daily_loss_pct}%
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Max Lot Size</span>
                                    <span className="text-slate-100">{riskLimits.max_lot_size}</span>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                )}
            </div>

            {/* Execute Trade from Setup Button */}
            {currentSetup && onExecuteTrade && (
                <div className="p-3 border-t border-slate-800">
                    <Button
                        className="w-full h-9"
                        variant={currentSetup.direction === 'LONG' ? 'default' : 'destructive'}
                        onClick={() => onExecuteTrade({
                            symbol: currentSetup.symbol,
                            order_type: currentSetup.direction === 'LONG' ? 'MARKET_BUY' : 'MARKET_SELL',
                            stop_loss: currentSetup.stop_loss,
                            take_profit: currentSetup.take_profit,
                        })}
                        disabled={!riskLimits?.can_trade || mode?.mode === 'ANALYSIS_ONLY'}
                    >
                        {currentSetup.direction === 'LONG' ? (
                            <TrendingUp className="w-4 h-4 mr-2" />
                        ) : (
                            <TrendingDown className="w-4 h-4 mr-2" />
                        )}
                        Execute {currentSetup.direction} {currentSetup.symbol}
                    </Button>
                </div>
            )}

            {/* Emergency Stop Button */}
            <div className="p-3 border-t border-slate-800">
                {positions.length > 0 && (
                    <AlertDialog>
                        <AlertDialogTrigger asChild>
                            <Button
                                variant="destructive"
                                className="w-full h-10 text-sm font-semibold"
                                disabled={emergencyStopMutation.isPending}
                            >
                                <Ban className="w-4 h-4 mr-2" />
                                {emergencyStopMutation.isPending ? 'CLOSING ALL...' : 'EMERGENCY STOP'}
                            </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent className="bg-slate-900 border-slate-800">
                            <AlertDialogHeader>
                                <AlertDialogTitle className="text-red-400 flex items-center gap-2">
                                    <AlertTriangle className="w-5 h-5" />
                                    Emergency Stop
                                </AlertDialogTitle>
                                <AlertDialogDescription className="text-slate-400">
                                    This will immediately:
                                    <ul className="list-disc list-inside mt-2 space-y-1">
                                        <li>Close ALL open positions ({positions.length})</li>
                                        <li>Cancel ALL pending orders ({orders.length})</li>
                                        <li>Block ALL new trades until reset</li>
                                    </ul>
                                    <div className="mt-3 text-yellow-400">
                                        Are you absolutely sure?
                                    </div>
                                </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                                <AlertDialogCancel className="bg-slate-800 border-slate-700">
                                    Cancel
                                </AlertDialogCancel>
                                <AlertDialogAction
                                    className="bg-red-600 hover:bg-red-700"
                                    onClick={() => emergencyStopMutation.mutate()}
                                >
                                    CONFIRM EMERGENCY STOP
                                </AlertDialogAction>
                            </AlertDialogFooter>
                        </AlertDialogContent>
                    </AlertDialog>
                )}

                {positions.length === 0 && orders.length === 0 && (
                    <div className="text-center text-slate-500 text-xs">
                        <Shield className="w-4 h-4 mx-auto mb-1" />
                        No active positions or orders
                    </div>
                )}
            </div>
        </div>
    );
}

// Position Card Component
function PositionCard({
    position,
    onClose,
    isClosing
}: {
    position: Position;
    onClose: (ticket: number, volume?: number) => void;
    isClosing: boolean;
}) {
    return (
        <Card className="bg-slate-900/50 border-slate-800">
            <CardContent className="p-3">
                <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                        <Badge
                            variant="outline"
                            className={cn(
                                "text-xs",
                                position.type === 'BUY'
                                    ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50"
                                    : "bg-red-500/20 text-red-400 border-red-500/50"
                            )}
                        >
                            {position.type}
                        </Badge>
                        <span className="text-sm font-medium text-slate-100">{position.symbol}</span>
                        <span className="text-xs text-slate-500">{position.volume} lots</span>
                    </div>
                    <span className={cn(
                        "text-sm font-semibold",
                        position.profit >= 0 ? "text-emerald-400" : "text-red-400"
                    )}>
                        {position.profit >= 0 ? '+' : ''}${position.profit.toFixed(2)}
                    </span>
                </div>

                <div className="grid grid-cols-4 gap-2 text-xs mb-2">
                    <div>
                        <div className="text-slate-500">Entry</div>
                        <div className="text-slate-300">{position.open_price.toFixed(5)}</div>
                    </div>
                    <div>
                        <div className="text-slate-500">Current</div>
                        <div className="text-slate-300">{position.current_price.toFixed(5)}</div>
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

                {position.pips !== undefined && (
                    <div className="text-xs text-slate-500 mb-2">
                        {position.pips >= 0 ? '+' : ''}{position.pips.toFixed(1)} pips
                    </div>
                )}

                <div className="flex gap-2">
                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="h-7 text-xs flex-1 border-slate-700"
                                    disabled
                                >
                                    <Edit2 className="w-3 h-3 mr-1" />
                                    Modify
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                                <p>Modify SL/TP (coming soon)</p>
                            </TooltipContent>
                        </Tooltip>
                    </TooltipProvider>

                    <AlertDialog>
                        <AlertDialogTrigger asChild>
                            <Button
                                variant="destructive"
                                size="sm"
                                className="h-7 text-xs flex-1"
                                disabled={isClosing}
                            >
                                <X className="w-3 h-3 mr-1" />
                                Close
                            </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent className="bg-slate-900 border-slate-800">
                            <AlertDialogHeader>
                                <AlertDialogTitle>Close Position</AlertDialogTitle>
                                <AlertDialogDescription>
                                    Close {position.type} {position.symbol} ({position.volume} lots)?
                                    <br />
                                    Current P&L: <span className={position.profit >= 0 ? "text-emerald-400" : "text-red-400"}>
                                        {position.profit >= 0 ? '+' : ''}${position.profit.toFixed(2)}
                                    </span>
                                </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                                <AlertDialogCancel className="bg-slate-800 border-slate-700">
                                    Cancel
                                </AlertDialogCancel>
                                <AlertDialogAction
                                    className="bg-red-600 hover:bg-red-700"
                                    onClick={() => onClose(position.ticket)}
                                >
                                    Close Position
                                </AlertDialogAction>
                            </AlertDialogFooter>
                        </AlertDialogContent>
                    </AlertDialog>
                </div>
            </CardContent>
        </Card>
    );
}

// Order Card Component
function OrderCard({
    order,
    onCancel,
    isCancelling
}: {
    order: PendingOrder;
    onCancel: (ticket: number) => void;
    isCancelling: boolean;
}) {
    return (
        <Card className="bg-slate-900/50 border-slate-800">
            <CardContent className="p-3">
                <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs bg-blue-500/20 text-blue-400 border-blue-500/50">
                            {order.order_type}
                        </Badge>
                        <span className="text-sm font-medium text-slate-100">{order.symbol}</span>
                        <span className="text-xs text-slate-500">{order.volume} lots</span>
                    </div>
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs mb-2">
                    <div>
                        <div className="text-slate-500">Price</div>
                        <div className="text-blue-400">{order.price.toFixed(5)}</div>
                    </div>
                    <div>
                        <div className="text-slate-500">SL</div>
                        <div className="text-red-400">{order.stop_loss.toFixed(5)}</div>
                    </div>
                    <div>
                        <div className="text-slate-500">TP</div>
                        <div className="text-emerald-400">
                            {order.take_profit ? order.take_profit.toFixed(5) : '-'}
                        </div>
                    </div>
                </div>

                <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs w-full border-slate-700"
                    onClick={() => onCancel(order.ticket)}
                    disabled={isCancelling}
                >
                    <X className="w-3 h-3 mr-1" />
                    Cancel Order
                </Button>
            </CardContent>
        </Card>
    );
}
