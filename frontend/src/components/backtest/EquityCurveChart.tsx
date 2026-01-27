'use client';

import { useMemo } from 'react';
import { Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Area, ComposedChart } from 'recharts';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface EquityCurveProps {
    data: Array<{ timestamp: string; equity: number }>;
    maxDrawdownR: number;
    totalPnlR: number;
    className?: string;
}

export function EquityCurveChart({ data, maxDrawdownR, totalPnlR, className = '' }: EquityCurveProps) {
    const chartData = useMemo(() => {
        if (!data || data.length === 0) return [];

        // Calculate running high for drawdown visualization
        let runningHigh = 0;
        return data.map((point) => {
            runningHigh = Math.max(runningHigh, point.equity);
            return {
                timestamp: new Date(point.timestamp).toLocaleDateString(),
                equity: point.equity,
                highWaterMark: runningHigh,
                drawdown: point.equity - runningHigh
            };
        });
    }, [data]);

    const minEquity = useMemo(() => {
        if (chartData.length === 0) return 0;
        return Math.min(...chartData.map(d => d.equity));
    }, [chartData]);

    const maxEquity = useMemo(() => {
        if (chartData.length === 0) return 0;
        return Math.max(...chartData.map(d => d.equity));
    }, [chartData]);

    const isPositive = totalPnlR >= 0;

    if (!data || data.length === 0) {
        return (
            <div className={`bg-slate-800 rounded-lg p-4 ${className}`}>
                <div className="text-slate-500 text-center py-8">
                    No equity data available
                </div>
            </div>
        );
    }

    return (
        <div className={`bg-slate-800 rounded-lg p-4 ${className}`}>
            {/* Header with stats */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    {isPositive ? (
                        <TrendingUp className="w-5 h-5 text-green-400" />
                    ) : (
                        <TrendingDown className="w-5 h-5 text-red-400" />
                    )}
                    <span className="font-semibold text-white">Equity Curve</span>
                </div>
                <div className="flex items-center gap-4 text-sm">
                    <div>
                        <span className="text-slate-400">Total P&L: </span>
                        <span className={isPositive ? 'text-green-400' : 'text-red-400'}>
                            {totalPnlR > 0 ? '+' : ''}{totalPnlR.toFixed(2)}R
                        </span>
                    </div>
                    <div>
                        <span className="text-slate-400">Max DD: </span>
                        <span className="text-red-400">
                            {maxDrawdownR.toFixed(2)}R
                        </span>
                    </div>
                </div>
            </div>

            {/* Chart */}
            <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData}>
                        <defs>
                            <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop
                                    offset="5%"
                                    stopColor={isPositive ? "#22c55e" : "#ef4444"}
                                    stopOpacity={0.3}
                                />
                                <stop
                                    offset="95%"
                                    stopColor={isPositive ? "#22c55e" : "#ef4444"}
                                    stopOpacity={0}
                                />
                            </linearGradient>
                        </defs>

                        <XAxis
                            dataKey="timestamp"
                            stroke="#64748b"
                            tick={{ fill: '#64748b', fontSize: 10 }}
                            tickLine={false}
                        />
                        <YAxis
                            stroke="#64748b"
                            tick={{ fill: '#64748b', fontSize: 10 }}
                            tickLine={false}
                            domain={[Math.floor(minEquity - 1), Math.ceil(maxEquity + 1)]}
                            tickFormatter={(value: number) => `${value}R`}
                        />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: '#1e293b',
                                border: '1px solid #334155',
                                borderRadius: '8px'
                            }}
                            labelStyle={{ color: '#94a3b8' }}
                            formatter={(value: number) => [`${value.toFixed(2)}R`, 'Equity']}
                        />

                        {/* Zero line */}
                        <ReferenceLine
                            y={0}
                            stroke="#64748b"
                            strokeDasharray="3 3"
                        />

                        {/* High water mark */}
                        <Line
                            type="monotone"
                            dataKey="highWaterMark"
                            stroke="#8b5cf6"
                            strokeWidth={1}
                            strokeDasharray="5 5"
                            dot={false}
                            opacity={0.5}
                        />

                        {/* Equity area */}
                        <Area
                            type="monotone"
                            dataKey="equity"
                            stroke="none"
                            fill="url(#equityGradient)"
                        />

                        {/* Equity line */}
                        <Line
                            type="monotone"
                            dataKey="equity"
                            stroke={isPositive ? "#22c55e" : "#ef4444"}
                            strokeWidth={2}
                            dot={false}
                            activeDot={{ r: 4, fill: isPositive ? "#22c55e" : "#ef4444" }}
                        />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>

            {/* Legend */}
            <div className="flex items-center justify-center gap-6 mt-2 text-xs text-slate-400">
                <div className="flex items-center gap-1">
                    <div className={`w-3 h-0.5 ${isPositive ? 'bg-green-400' : 'bg-red-400'}`}></div>
                    <span>Equity</span>
                </div>
                <div className="flex items-center gap-1">
                    <div className="w-3 h-0.5 bg-purple-400 opacity-50" style={{ borderTop: '1px dashed' }}></div>
                    <span>High Water Mark</span>
                </div>
            </div>
        </div>
    );
}
