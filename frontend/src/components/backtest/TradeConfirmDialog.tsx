"use client";

import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Label } from "@/components/ui/label";
import {
    AlertTriangle,
    TrendingUp,
    TrendingDown,
    DollarSign,
    Target,
    Shield,
    Clock,
    Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
    placeOrder,
    validateOrder,
    getAccountInfo,
    getTradingConfig,
    OrderRequest,
    OrderResponse,
    TradeValidation,
    AccountInfo,
    TradingConfig,
    openTrade,
    OpenTradeRequest,
    OpenTradeResponse,
} from "@/lib/api";

interface TradeConfirmDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    order: Partial<OrderRequest> | null;
    onSuccess?: (response: any) => void;
    onError?: (error: Error) => void;
    backtestMode?: boolean;
}

export function TradeConfirmDialog({
    open,
    onOpenChange,
    order,
    onSuccess,
    onError,
    backtestMode = false,
}: TradeConfirmDialogProps) {
    // State
    const [confirmations, setConfirmations] = useState({
        understand_live: false,
        accept_risk: false,
        verified_setup: false,
    });
    const [countdown, setCountdown] = useState(5);

    // Fetch account info
    const { data: account } = useQuery({
        queryKey: ['accountInfo'],
        queryFn: getAccountInfo,
        enabled: open && !backtestMode,
    });

    // Fetch trading config
    const { data: tradingConfig } = useQuery({
        queryKey: ['tradingConfig'],
        queryFn: getTradingConfig,
        enabled: open && !backtestMode,
    });

    // Validate trade (skip for backtest for now, or implement backtest validation)
    const { data: validation, isLoading: validating } = useQuery({
        queryKey: ['validateOrder', order],
        queryFn: () => (order && !backtestMode) ? validateOrder(order as OrderRequest) : Promise.resolve(null),
        enabled: open && !!order && !backtestMode,
    });

    // Execute trade mutation - using unified session API
    const executeMutation = useMutation({
        mutationFn: async (req: Partial<OrderRequest>) => {
            if (backtestMode) {
                // Map OrderRequest to OpenTradeRequest (unified session API)
                const sessionReq: OpenTradeRequest = {
                    direction: (req.order_type === 'MARKET_BUY' || req.order_type === 'BUY_LIMIT' || req.order_type === 'BUY_STOP') ? 'LONG' : 'SHORT',
                    entry_price: req.price || 0, // Should be current price if market
                    stop_loss: req.stop_loss || 0,
                    take_profit: req.take_profit,
                    volume: req.volume,
                };

                return await openTrade(sessionReq);
            } else {
                return await placeOrder(req as OrderRequest);
            }
        },
        onSuccess: (response) => {
            onOpenChange(false);
            onSuccess?.(response);
        },
        onError: (error: Error) => {
            onError?.(error);
        },
    });

    // Reset state when dialog opens/closes
    useEffect(() => {
        if (open) {
            setConfirmations({
                understand_live: false,
                accept_risk: false,
                verified_setup: false,
            });
            setCountdown(tradingConfig?.safety?.confirmation_delay_seconds || 5);
        }
    }, [open, tradingConfig]);

    // Derive allChecked from confirmations
    const allChecked = Object.values(confirmations).every(Boolean);

    // Countdown runs automatically when all boxes are checked
    useEffect(() => {
        if (!allChecked || countdown <= 0) return;

        const timer = setInterval(() => {
            setCountdown((prev) => prev - 1);
        }, 1000);

        return () => clearInterval(timer);
    }, [allChecked, countdown]);

    // Calculate risk preview
    const calculateRiskPreview = useCallback(() => {
        if (!order || !account || !order.stop_loss) return null;

        const isLong = order.order_type === 'MARKET_BUY' ||
            order.order_type === 'BUY_LIMIT' ||
            order.order_type === 'BUY_STOP';

        // Estimate entry price (for market orders, use current price approximation)
        const entryPrice = order.price || 0;
        const slDistance = Math.abs(entryPrice - order.stop_loss);
        const tpDistance = order.take_profit ? Math.abs(order.take_profit - entryPrice) : 0;

        // Risk-reward ratio
        const riskReward = tpDistance > 0 && slDistance > 0 ? tpDistance / slDistance : 0;

        // Calculate dollar risk (rough estimate)
        const volume = order.volume || 0.01;
        // Approximate pip value for forex
        const pipValue = 10 * volume; // $10 per pip per lot for most pairs
        const slPips = slDistance * 10000; // Convert to pips
        const riskDollars = slPips * pipValue;
        const riskPercent = account.balance > 0 ? (riskDollars / account.balance) * 100 : 0;

        return {
            riskDollars,
            riskPercent,
            riskReward,
            isLong,
        };
    }, [order, account]);

    const riskPreview = calculateRiskPreview();

    // Determine if it's a large trade
    const isLargeTrade = order?.volume !== undefined &&
        tradingConfig?.safety?.large_trade_threshold_lots !== undefined &&
        order.volume >= tradingConfig.safety.large_trade_threshold_lots;

    // Can execute?
    const allConfirmed = backtestMode || Object.values(confirmations).every(Boolean);
    const countdownComplete = backtestMode || countdown <= 0;
    const validationPassed = backtestMode || (validation?.valid ?? false);
    const canExecute = allConfirmed && countdownComplete && validationPassed && !executeMutation.isPending;

    // Handle execute
    const handleExecute = () => {
        if (!order || !canExecute) return;
        executeMutation.mutate(order as OrderRequest);
    };

    if (!order) return null;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="bg-slate-900 border-slate-800 sm:max-w-lg">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2 text-lg">
                        {order.order_type?.includes('BUY') ? (
                            <TrendingUp className="w-5 h-5 text-emerald-400" />
                        ) : (
                            <TrendingDown className="w-5 h-5 text-red-400" />
                        )}
                        Confirm {backtestMode ? 'Backtest' : 'Live'} Trade Execution
                    </DialogTitle>
                    <DialogDescription className="text-slate-400">
                        Review and confirm your trade details before execution.
                    </DialogDescription>
                </DialogHeader>

                {/* Trade Summary */}
                <div className="space-y-4">
                    <div className="bg-slate-950 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                                <Badge
                                    variant="outline"
                                    className={cn(
                                        "text-sm",
                                        order.order_type?.includes('BUY')
                                            ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50"
                                            : "bg-red-500/20 text-red-400 border-red-500/50"
                                    )}
                                >
                                    {order.order_type}
                                </Badge>
                                <span className="text-lg font-semibold text-white">{order.symbol}</span>
                            </div>
                            {order.volume && (
                                <span className="text-slate-400">
                                    {order.volume} lots
                                </span>
                            )}
                        </div>

                        <div className="grid grid-cols-3 gap-4 text-sm">
                            <div>
                                <div className="text-slate-500 mb-1">Stop Loss</div>
                                <div className="text-red-400 font-medium">
                                    {order.stop_loss?.toFixed(5)}
                                </div>
                            </div>
                            <div>
                                <div className="text-slate-500 mb-1">Take Profit</div>
                                <div className="text-emerald-400 font-medium">
                                    {order.take_profit?.toFixed(5) || 'Not set'}
                                </div>
                            </div>
                            <div>
                                <div className="text-slate-500 mb-1">Entry</div>
                                <div className="text-blue-400 font-medium">
                                    {order.price ? order.price.toFixed(5) : 'Market'}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Risk Preview */}
                    {riskPreview && !backtestMode && (
                        <div className="bg-slate-950 rounded-lg p-4">
                            <div className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-2">
                                <Shield className="w-4 h-4" />
                                Risk Preview
                            </div>
                            <div className="grid grid-cols-3 gap-4 text-sm">
                                <div>
                                    <div className="text-slate-500 mb-1">Dollar Risk</div>
                                    <div className="text-red-400 font-medium">
                                        ${riskPreview.riskDollars.toFixed(2)}
                                    </div>
                                </div>
                                <div>
                                    <div className="text-slate-500 mb-1">% of Account</div>
                                    <div className={cn(
                                        "font-medium",
                                        riskPreview.riskPercent > 2 ? "text-red-400" : "text-yellow-400"
                                    )}>
                                        {riskPreview.riskPercent.toFixed(2)}%
                                    </div>
                                </div>
                                <div>
                                    <div className="text-slate-500 mb-1">R:R Ratio</div>
                                    <div className={cn(
                                        "font-medium",
                                        riskPreview.riskReward >= 2 ? "text-emerald-400" : "text-yellow-400"
                                    )}>
                                        {riskPreview.riskReward > 0 ? `1:${riskPreview.riskReward.toFixed(1)}` : 'N/A'}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Validation Results */}
                    {validating && (
                        <div className="flex items-center gap-2 text-sm text-slate-400">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Validating trade...
                        </div>
                    )}

                    {validation && !validation.valid && (
                        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                            <div className="flex items-center gap-2 text-red-400 font-medium mb-2">
                                <AlertTriangle className="w-4 h-4" />
                                Validation Failed
                            </div>
                            <ul className="text-sm text-red-300 space-y-1">
                                {validation.errors.map((error, i) => (
                                    <li key={i}>• {error}</li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {validation?.warnings && validation.warnings.length > 0 && (
                        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
                            <div className="flex items-center gap-2 text-yellow-400 font-medium mb-2">
                                <AlertTriangle className="w-4 h-4" />
                                Warnings
                            </div>
                            <ul className="text-sm text-yellow-300 space-y-1">
                                {validation.warnings.map((warning, i) => (
                                    <li key={i}>• {warning}</li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Warning Banner */}
                    {!backtestMode && (
                        <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-3 flex items-start gap-3">
                            <AlertTriangle className="w-5 h-5 text-orange-400 flex-shrink-0 mt-0.5" />
                            <div className="text-sm text-orange-300">
                                <strong>Trading involves substantial risk of loss.</strong>
                                <br />
                                Only trade with capital you can afford to lose.
                            </div>
                        </div>
                    )}

                    {!backtestMode && <Separator className="bg-slate-800" />}

                    {/* Confirmation Checkboxes - Hidden in Backtest Mode */}
                    {!backtestMode && (
                        <div className="space-y-3">
                            <div className="flex items-center space-x-3">
                                <Checkbox
                                    id="understand_live"
                                    checked={confirmations.understand_live}
                                    onCheckedChange={(checked) =>
                                        setConfirmations(prev => ({ ...prev, understand_live: !!checked }))
                                    }
                                    className="border-slate-600 data-[state=checked]:bg-blue-500"
                                />
                                <Label htmlFor="understand_live" className="text-sm text-slate-300 cursor-pointer">
                                    I understand this is a <strong className="text-white">LIVE trade</strong> with real money
                                </Label>
                            </div>

                            <div className="flex items-center space-x-3">
                                <Checkbox
                                    id="accept_risk"
                                    checked={confirmations.accept_risk}
                                    onCheckedChange={(checked) =>
                                        setConfirmations(prev => ({ ...prev, accept_risk: !!checked }))
                                    }
                                    className="border-slate-600 data-[state=checked]:bg-blue-500"
                                />
                                <Label htmlFor="accept_risk" className="text-sm text-slate-300 cursor-pointer">
                                    I <strong className="text-white">accept the risk of loss</strong> on this trade
                                </Label>
                            </div>

                            <div className="flex items-center space-x-3">
                                <Checkbox
                                    id="verified_setup"
                                    checked={confirmations.verified_setup}
                                    onCheckedChange={(checked) =>
                                        setConfirmations(prev => ({ ...prev, verified_setup: !!checked }))
                                    }
                                    className="border-slate-600 data-[state=checked]:bg-blue-500"
                                />
                                <Label htmlFor="verified_setup" className="text-sm text-slate-300 cursor-pointer">
                                    I have <strong className="text-white">verified the trade setup</strong> is correct
                                </Label>
                            </div>
                        </div>
                    )}

                    {/* Large Trade Warning */}
                    {isLargeTrade && tradingConfig?.safety?.double_confirm_large_trades && !backtestMode && (
                        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 flex items-center gap-3">
                            <AlertTriangle className="w-5 h-5 text-red-400" />
                            <div className="text-sm text-red-300">
                                <strong>Large Trade Alert:</strong> This trade exceeds the large trade threshold
                                ({tradingConfig.safety.large_trade_threshold_lots} lots).
                            </div>
                        </div>
                    )}
                </div>

                <DialogFooter className="gap-2 sm:gap-0">
                    <Button
                        variant="outline"
                        onClick={() => onOpenChange(false)}
                        className="border-slate-700"
                        disabled={executeMutation.isPending}
                    >
                        Cancel
                    </Button>

                    <Button
                        variant={order.order_type?.includes('BUY') ? 'default' : 'destructive'}
                        onClick={handleExecute}
                        disabled={!canExecute}
                        className={cn(
                            "min-w-[140px]",
                            !canExecute && "opacity-50"
                        )}
                    >
                        {executeMutation.isPending ? (
                            <>
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                Executing...
                            </>
                        ) : !allConfirmed ? (
                            <>
                                <Shield className="w-4 h-4 mr-2" />
                                Confirm All
                            </>
                        ) : !countdownComplete ? (
                            <>
                                <Clock className="w-4 h-4 mr-2" />
                                Wait {countdown}s
                            </>
                        ) : !validationPassed ? (
                            <>
                                <AlertTriangle className="w-4 h-4 mr-2" />
                                Invalid
                            </>
                        ) : (
                            <>
                                <Target className="w-4 h-4 mr-2" />
                                Execute Trade
                            </>
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
