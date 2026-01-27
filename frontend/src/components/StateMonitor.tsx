import React from 'react';
import { useTradingSession } from '@/hooks/useTradingSession';
import { AgentPhase } from '@/types/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Activity, RefreshCw, Play, RotateCcw, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

export function StateMonitor() {
    const {
        phase,
        lastTick,
        isLoading,
        isError,
        error,
        manualTick,
        resetSession
    } = useTradingSession(1000); // 1s polling

    if (isLoading && !lastTick) {
        return <div className="p-4 text-center">Loading Agent State...</div>;
    }

    if (isError) {
        return (
            <Card className="border-red-500 bg-red-50">
                <CardHeader>
                    <CardTitle className="text-red-700 flex items-center gap-2">
                        <AlertCircle className="h-5 w-5" />
                        Connection Error
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <p className="text-red-600 mb-4">{error}</p>
                    <Button variant="outline" onClick={() => window.location.reload()}>
                        Retry Connection
                    </Button>
                </CardContent>
            </Card>
        );
    }

    // Phase Stepper Logic
    const phases = [
        AgentPhase.IDLE,
        AgentPhase.ANALYZING,
        AgentPhase.DECIDING,
        AgentPhase.EXECUTING
    ];

    const isBooting = phase === AgentPhase.BOOTING;
    const isWaiting = phase === AgentPhase.WAITING;

    // Reliability Metrics (Mocked for now based on API/Hook limitations)
    const pendingRequests = isWaiting ? 1 : 0;
    const retryCount = 0; // Placeholder

    return (
        <Card className="w-full max-w-4xl mx-auto shadow-lg">
            <CardHeader className="border-b bg-muted/20">
                <div className="flex justify-between items-center">
                    <div>
                        <CardTitle className="flex items-center gap-2 text-xl">
                            <Activity className="h-5 w-5 text-blue-500" />
                            Agent Neural State
                        </CardTitle>
                        <CardDescription>
                            Real-time monitoring of agent decision process
                        </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono">
                            Tick: {lastTick}
                        </Badge>
                        <Badge variant={isWaiting ? "secondary" : "default"} className={cn(
                            isWaiting && "animate-pulse bg-yellow-500 text-yellow-950",
                            phase === AgentPhase.EXECUTING && "bg-green-600"
                        )}>
                            Status: {phase}
                        </Badge>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="p-6 space-y-8">
                {/* Phase Indicator */}
                <div className="relative">
                    <div className="absolute top-1/2 left-0 w-full h-1 bg-gray-200 -z-10 transform -translate-y-1/2" />
                    <div className="flex justify-between">
                        {phases.map((p) => {
                            const isActive = phase === p;
                            // If we are at EXECUTING, all previous should be completed? 
                            // For simplicity, we just highlight current.
                            // Logic: Active is Green.

                            let badgeClass = "bg-gray-100 text-gray-400 border-gray-300";
                            if (isActive) {
                                badgeClass = "bg-green-100 text-green-700 border-green-500 ring-2 ring-green-500/20";
                            }
                            if (isBooting && p === AgentPhase.IDLE) {
                                badgeClass = "bg-blue-100 text-blue-700 border-blue-500 animate-pulse";
                            }

                            return (
                                <div key={p} className="flex flex-col items-center gap-2 bg-background px-2">
                                    <div className={cn(
                                        "w-8 h-8 rounded-full flex items-center justify-center border-2 font-bold transition-all duration-300",
                                        badgeClass
                                    )}>
                                        {isActive && <div className="w-2 h-2 rounded-full bg-green-500 animate-ping" />}
                                    </div>
                                    <span className={cn(
                                        "text-xs font-medium uppercase tracking-wider",
                                        isActive ? "text-green-700" : "text-gray-500"
                                    )}>
                                        {p}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Reliability Nervous System */}
                <div className="grid grid-cols-3 gap-4 p-4 bg-slate-50 rounded-lg border border-slate-100">
                    <div className="flex flex-col items-center justify-center border-r border-slate-200 last:border-0">
                        <span className="text-xs text-slate-400 uppercase font-semibold">Pending Requests</span>
                        <span className="text-2xl font-mono text-slate-700">{pendingRequests}</span>
                    </div>
                    <div className="flex flex-col items-center justify-center border-r border-slate-200 last:border-0">
                        <span className="text-xs text-slate-400 uppercase font-semibold">Retry Count</span>
                        <span className="text-2xl font-mono text-slate-700">{retryCount}</span>
                    </div>
                    <div className="flex flex-col items-center justify-center">
                        <span className="text-xs text-slate-400 uppercase font-semibold">Session Mode</span>
                        <span className="text-sm font-bold text-slate-700">BACKTEST</span>
                    </div>
                </div>

                {/* Control Panel */}
                <div className="flex items-center justify-between gap-4 pt-4 border-t">
                    <Button
                        variant="destructive"
                        size="sm"
                        onClick={resetSession}
                        disabled={isLoading}
                        className="gap-2"
                    >
                        <RotateCcw className="h-4 w-4" />
                        Reset Session
                    </Button>

                    <Button
                        size="lg"
                        className={cn(
                            "gap-2 min-w-[200px] transition-all",
                            isWaiting ? "bg-yellow-500 hover:bg-yellow-600" : "bg-blue-600 hover:bg-blue-700"
                        )}
                        onClick={manualTick}
                        disabled={isLoading || isWaiting}
                    >
                        {isWaiting ? (
                            <>
                                <RefreshCw className="h-5 w-5 animate-spin" />
                                Processing...
                            </>
                        ) : (
                            <>
                                <Play className="h-5 w-5 fill-current" />
                                Advance Tick
                            </>
                        )}
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}
