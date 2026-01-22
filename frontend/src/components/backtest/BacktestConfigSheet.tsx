"use client";

import { useState } from "react";
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TradingPairSelector } from "@/components/dashboard/TradingPairSelector";
import { Separator } from "@/components/ui/separator";
import { Calendar, Save } from "lucide-react";

interface BacktestConfig {
    symbol: string;
    fromDate: string;
    toDate: string;
    timeframes: string[];
}

interface BacktestConfigSheetProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    config: BacktestConfig;
    onConfigChange: (config: BacktestConfig) => void;
    onApply: () => void;
    mt5Symbols?: string[];
}

export function BacktestConfigSheet({
    open,
    onOpenChange,
    config,
    onConfigChange,
    onApply,
    mt5Symbols,
}: BacktestConfigSheetProps) {
    const updateConfig = (partial: Partial<BacktestConfig>) => {
        onConfigChange({ ...config, ...partial });
    };

    // Quick date presets
    const setDateRange = (days: number) => {
        const toDate = new Date();
        const fromDate = new Date();
        fromDate.setDate(fromDate.getDate() - days);
        updateConfig({
            fromDate: fromDate.toISOString().split('T')[0],
            toDate: toDate.toISOString().split('T')[0],
        });
    };

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent className="bg-slate-900 border-slate-800 w-[350px]">
                <SheetHeader>
                    <SheetTitle className="text-slate-100 flex items-center gap-2">
                        <Calendar className="w-5 h-5 text-blue-400" />
                        Backtest Configuration
                    </SheetTitle>
                    <SheetDescription className="text-slate-400">
                        Configure the backtest parameters and date range
                    </SheetDescription>
                </SheetHeader>

                <div className="space-y-6 mt-6">
                    {/* Symbol Selection */}
                    <div className="space-y-2">
                        <Label className="text-sm text-slate-300">Symbol</Label>
                        <TradingPairSelector
                            value={config.symbol}
                            onChange={(symbol) => updateConfig({ symbol })}
                            className="w-full"
                            mt5Symbols={mt5Symbols}
                        />
                    </div>

                    <Separator className="bg-slate-800" />

                    {/* Date Range */}
                    <div className="space-y-3">
                        <Label className="text-sm text-slate-300">Date Range</Label>
                        
                        {/* Quick Presets */}
                        <div className="flex gap-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setDateRange(1)}
                                className="flex-1 h-7 text-xs border-slate-700"
                            >
                                1D
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setDateRange(7)}
                                className="flex-1 h-7 text-xs border-slate-700"
                            >
                                1W
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setDateRange(30)}
                                className="flex-1 h-7 text-xs border-slate-700"
                            >
                                1M
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setDateRange(90)}
                                className="flex-1 h-7 text-xs border-slate-700"
                            >
                                3M
                            </Button>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1.5">
                                <Label className="text-xs text-slate-500">From</Label>
                                <Input
                                    type="date"
                                    value={config.fromDate}
                                    onChange={(e) => updateConfig({ fromDate: e.target.value })}
                                    className="bg-slate-800 border-slate-700 h-9"
                                />
                            </div>
                            <div className="space-y-1.5">
                                <Label className="text-xs text-slate-500">To</Label>
                                <Input
                                    type="date"
                                    value={config.toDate}
                                    onChange={(e) => updateConfig({ toDate: e.target.value })}
                                    className="bg-slate-800 border-slate-700 h-9"
                                />
                            </div>
                        </div>
                    </div>

                    <Separator className="bg-slate-800" />

                    {/* Timeframes */}
                    <div className="space-y-2">
                        <Label className="text-sm text-slate-300">Timeframes</Label>
                        <div className="flex flex-wrap gap-2">
                            {["1H", "15M", "5M", "1M"].map((tf) => (
                                <Button
                                    key={tf}
                                    variant="outline"
                                    size="sm"
                                    onClick={() => {
                                        const newTfs = config.timeframes.includes(tf)
                                            ? config.timeframes.filter(t => t !== tf)
                                            : [...config.timeframes, tf];
                                        updateConfig({ timeframes: newTfs });
                                    }}
                                    className={`h-7 text-xs ${
                                        config.timeframes.includes(tf)
                                            ? "bg-blue-600 border-blue-500 text-white hover:bg-blue-700"
                                            : "border-slate-700"
                                    }`}
                                >
                                    {tf}
                                </Button>
                            ))}
                        </div>
                        <p className="text-[10px] text-slate-500">
                            Select timeframes to load for analysis
                        </p>
                    </div>

                    <Separator className="bg-slate-800" />

                    {/* Apply Button */}
                    <Button
                        onClick={() => {
                            onApply();
                            onOpenChange(false);
                        }}
                        className="w-full bg-emerald-600 hover:bg-emerald-700"
                    >
                        <Save className="w-4 h-4 mr-2" />
                        Apply & Load Data
                    </Button>
                </div>
            </SheetContent>
        </Sheet>
    );
}
