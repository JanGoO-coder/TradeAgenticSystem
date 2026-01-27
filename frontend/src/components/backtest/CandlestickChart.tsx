"use client";

import { useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { CandlestickChart as ChartIcon, TrendingUp, TrendingDown } from "lucide-react";

interface OHLCV {
    timestamp: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

interface PriceLevel {
    price: number;
    label: string;
    type: "entry" | "stop" | "target" | "invalidation";
}

interface CandlestickChartProps {
    data: Record<string, OHLCV[]>;
    selectedTimeframe: string;
    onTimeframeChange: (tf: string) => void;
    priceLevels?: PriceLevel[];
    symbol: string;
    className?: string;
}

// Simple candlestick visualization using divs
function Candle({
    candle,
    minPrice,
    maxPrice,
    width
}: {
    candle: OHLCV;
    minPrice: number;
    maxPrice: number;
    width: number;
}) {
    const range = maxPrice - minPrice;
    if (range === 0) return null;

    const isBullish = candle.close >= candle.open;
    const bodyTop = Math.max(candle.open, candle.close);
    const bodyBottom = Math.min(candle.open, candle.close);

    const highPercent = ((maxPrice - candle.high) / range) * 100;
    const lowPercent = ((maxPrice - candle.low) / range) * 100;
    const bodyTopPercent = ((maxPrice - bodyTop) / range) * 100;
    const bodyBottomPercent = ((maxPrice - bodyBottom) / range) * 100;
    const bodyHeight = bodyBottomPercent - bodyTopPercent;

    return (
        <div className="relative h-full flex flex-col items-center" style={{ width: `${width}px` }}>
            {/* Wick */}
            <div
                className={`absolute w-px ${isBullish ? 'bg-emerald-500' : 'bg-red-500'}`}
                style={{
                    top: `${highPercent}%`,
                    height: `${lowPercent - highPercent}%`
                }}
            />
            {/* Body */}
            <div
                className={`absolute rounded-sm ${isBullish ? 'bg-emerald-500' : 'bg-red-500'}`}
                style={{
                    top: `${bodyTopPercent}%`,
                    height: `${Math.max(bodyHeight, 1)}%`,
                    width: `${Math.max(width - 2, 2)}px`
                }}
            />
        </div>
    );
}

// Price level line - always renders if within expanded range (includes price levels)
function PriceLevelLine({
    level,
    minPrice,
    maxPrice
}: {
    level: PriceLevel;
    minPrice: number;
    maxPrice: number;
}) {
    const range = maxPrice - minPrice;
    if (range === 0) return null;

    // Calculate position - clamp between 0% and 100% to keep label visible at edges
    const topPercent = ((maxPrice - level.price) / range) * 100;
    const clampedTop = Math.max(0, Math.min(100, topPercent));

    // Determine if level is outside visible range (for visual indication)
    const isAboveRange = level.price > maxPrice;
    const isBelowRange = level.price < minPrice;
    const isOutOfRange = isAboveRange || isBelowRange;

    const colors = {
        entry: "border-blue-500 bg-blue-500/20 text-blue-400",
        stop: "border-red-500 bg-red-500/20 text-red-400",
        target: "border-emerald-500 bg-emerald-500/20 text-emerald-400",
        invalidation: "border-orange-500 bg-orange-500/20 text-orange-400",
    };

    const lineColors = {
        entry: "border-blue-500",
        stop: "border-red-500",
        target: "border-emerald-500",
        invalidation: "border-orange-500",
    };

    return (
        <div
            className={`absolute left-0 right-0 border-t border-dashed ${lineColors[level.type]} z-10 ${isOutOfRange ? 'opacity-60' : ''}`}
            style={{ top: `${clampedTop}%` }}
        >
            <span className={`absolute right-0 text-[10px] px-1 rounded ${colors[level.type]} -translate-y-1/2`}>
                {level.label}: {level.price.toFixed(5)}
                {isAboveRange && ' ↑'}
                {isBelowRange && ' ↓'}
            </span>
        </div>
    );
}

export function CandlestickChart({
    data,
    selectedTimeframe,
    onTimeframeChange,
    priceLevels = [],
    symbol,
    className = ""
}: CandlestickChartProps) {
    const timeframes = Object.keys(data).filter(tf => data[tf]?.length > 0);
    const candles = data[selectedTimeframe] || [];

    // Calculate price range - ALWAYS include price levels for consistent display across timeframes
    const { minPrice, maxPrice, lastCandle, priceChange } = useMemo(() => {
        if (candles.length === 0) {
            // If no candles but we have price levels, use those
            if (priceLevels.length > 0) {
                let min = Math.min(...priceLevels.map(l => l.price));
                let max = Math.max(...priceLevels.map(l => l.price));
                const padding = (max - min) * 0.1 || 0.001;
                return { minPrice: min - padding, maxPrice: max + padding, lastCandle: null, priceChange: 0 };
            }
            return { minPrice: 0, maxPrice: 0, lastCandle: null, priceChange: 0 };
        }

        // Start with candle range
        let min = Infinity;
        let max = -Infinity;

        candles.forEach(c => {
            if (c.low < min) min = c.low;
            if (c.high > max) max = c.high;
        });

        // ALWAYS include price levels in range to ensure they're visible
        if (priceLevels.length > 0) {
            priceLevels.forEach(level => {
                // Expand range to fit all price levels
                if (level.price < min) min = level.price;
                if (level.price > max) max = level.price;
            });
        }

        // Add 8% padding for better visibility (increased from 5%)
        const padding = (max - min) * 0.08;
        min -= padding;
        max += padding;

        const last = candles[candles.length - 1];
        const first = candles[0];
        const change = first ? ((last.close - first.open) / first.open) * 100 : 0;

        return { minPrice: min, maxPrice: max, lastCandle: last, priceChange: change };
    }, [candles, priceLevels]);

    // Visible candles (show last N based on width)
    const maxCandles = 60;
    const visibleCandles = candles.slice(-maxCandles);
    const candleWidth = Math.max(4, Math.min(12, 600 / maxCandles));

    if (timeframes.length === 0) {
        return (
            <Card className={`bg-slate-900 border-slate-800 ${className}`}>
                <CardContent className="flex items-center justify-center h-full min-h-[300px]">
                    <div className="text-center text-slate-500">
                        <ChartIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                        <p>No chart data available</p>
                        <p className="text-xs mt-1">Load backtest data to view charts</p>
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className={`bg-slate-900 border-slate-800 flex flex-col ${className}`}>
            <CardHeader className="pb-2 flex-shrink-0">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
                            <ChartIcon className="w-4 h-4" />
                            {symbol}
                        </CardTitle>
                        {lastCandle && (
                            <div className="flex items-center gap-2">
                                <span className="text-lg font-mono text-slate-100">
                                    {lastCandle.close.toFixed(5)}
                                </span>
                                <Badge
                                    variant="outline"
                                    className={priceChange >= 0
                                        ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50"
                                        : "bg-red-500/20 text-red-400 border-red-500/50"
                                    }
                                >
                                    {priceChange >= 0 ? <TrendingUp className="w-3 h-3 mr-1" /> : <TrendingDown className="w-3 h-3 mr-1" />}
                                    {priceChange >= 0 ? "+" : ""}{priceChange.toFixed(2)}%
                                </Badge>
                            </div>
                        )}
                    </div>
                    <Tabs value={selectedTimeframe} onValueChange={onTimeframeChange}>
                        <TabsList className="bg-slate-800 h-7">
                            {timeframes.map(tf => (
                                <TabsTrigger
                                    key={tf}
                                    value={tf}
                                    className="text-xs px-2 h-5 data-[state=active]:bg-slate-700"
                                >
                                    {tf}
                                </TabsTrigger>
                            ))}
                        </TabsList>
                    </Tabs>
                </div>
            </CardHeader>
            <CardContent className="flex-1 pt-2 pb-3 px-3">
                <div className="relative h-full min-h-[200px] bg-slate-950 rounded-lg p-2 overflow-hidden">
                    {/* Y-axis labels */}
                    <div className="absolute left-0 top-0 bottom-0 w-16 flex flex-col justify-between text-[10px] text-slate-500 font-mono py-2">
                        <span>{maxPrice.toFixed(5)}</span>
                        <span>{((maxPrice + minPrice) / 2).toFixed(5)}</span>
                        <span>{minPrice.toFixed(5)}</span>
                    </div>

                    {/* Chart area */}
                    <div className="absolute left-16 right-2 top-2 bottom-6 overflow-hidden">
                        {/* Price level lines */}
                        {priceLevels.map((level, i) => (
                            <PriceLevelLine
                                key={`${level.label}-${i}`}
                                level={level}
                                minPrice={minPrice}
                                maxPrice={maxPrice}
                            />
                        ))}

                        {/* Candles */}
                        <div className="flex items-end justify-end h-full gap-px">
                            {visibleCandles.map((candle, i) => (
                                <Candle
                                    key={candle.timestamp}
                                    candle={candle}
                                    minPrice={minPrice}
                                    maxPrice={maxPrice}
                                    width={candleWidth}
                                />
                            ))}
                        </div>
                    </div>

                    {/* Time label - display in UTC to match control bar */}
                    {lastCandle && (
                        <div className="absolute bottom-1 right-2 text-[10px] text-slate-500">
                            {new Date(lastCandle.timestamp).toLocaleString("en-US", {
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                                timeZone: "UTC",
                            })} UTC
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
