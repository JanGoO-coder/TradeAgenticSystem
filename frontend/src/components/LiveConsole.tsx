import React, { useRef, useEffect } from 'react';
import { useTradingSession } from '@/hooks/useTradingSession';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Terminal, ArrowRight, ArrowLeft, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { AuditLogEntry } from '@/types/api';

export function LiveConsole() {
    const { auditLog } = useTradingSession(1000);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when logs update
    useEffect(() => {
        if (scrollRef.current) {
            const scrollElement = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]');
            if (scrollElement) {
                scrollElement.scrollTop = scrollElement.scrollHeight;
            }
        }
    }, [auditLog]);

    const getVariant = (entry: AuditLogEntry) => {
        const action = entry.action.toUpperCase();
        if (action.includes('ERROR') || action.includes('FAIL')) return 'error';
        if (action.includes('WARN') || action.includes('TIMEOUT')) return 'warning';
        if (action.includes('RECEIVE') || action.includes('ACK')) return 'success';
        return 'info';
    };

    const formatTimestamp = (ts: string) => {
        try {
            return new Date(ts).toLocaleTimeString('en-US', {
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                fractionalSecondDigits: 3
            });
        } catch (e) {
            return ts;
        }
    };

    return (
        <Card className="w-full h-full bg-[#0a0f1e] text-slate-300 border-slate-800 shadow-xl overflow-hidden flex flex-col">
            <CardHeader className="bg-[#12182b] border-b border-slate-800 py-3 px-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Terminal className="h-4 w-4 text-emerald-500" />
                        <CardTitle className="text-sm font-mono text-slate-100 uppercase tracking-widest">
                            Agent Neural Link
                        </CardTitle>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        LIVE
                    </div>
                </div>
            </CardHeader>

            <div className="flex-1 min-h-0 bg-[#0a0f1e] font-mono text-xs p-0 relative">
                <ScrollArea className="h-[400px]" ref={scrollRef}>
                    <div className="p-4 space-y-1.5 list-none">
                        {auditLog.length === 0 && (
                            <div className="text-slate-600 italic text-center py-10 opacity-50">
                                _awaiting_signal_stream...
                            </div>
                        )}

                        {auditLog.map((log) => {
                            const variant = getVariant(log);
                            let Icon = ArrowRight;
                            let colorClass = "text-blue-400";
                            let bgClass = "bg-blue-500/5";

                            if (variant === 'success') {
                                Icon = CheckCircle; // or ArrowLeft for received
                                colorClass = "text-emerald-400";
                                bgClass = "bg-emerald-500/5";
                            } else if (variant === 'warning') {
                                Icon = AlertTriangle;
                                colorClass = "text-yellow-400";
                                bgClass = "bg-yellow-500/5";
                            } else if (variant === 'error') {
                                Icon = AlertCircle;
                                colorClass = "text-red-400";
                                bgClass = "bg-red-500/10";
                            }

                            return (
                                <div key={log.id} className={cn(
                                    "flex items-start gap-3 py-1.5 px-2 rounded border-l-2 border-transparent hover:bg-slate-800/50 transition-colors group",
                                    variant === 'error' && "border-red-500/50 bg-red-950/20",
                                    variant === 'warning' && "border-yellow-500/50"
                                )}>
                                    <span className="text-slate-500 min-w-[90px] select-none text-[10px] pt-0.5">
                                        [{formatTimestamp(log.timestamp)}]
                                    </span>

                                    <div className={cn("flex items-center gap-1.5 font-bold uppercase min-w-[120px]", colorClass)}>
                                        <Icon className="h-3 w-3" />
                                        {log.action}
                                    </div>

                                    <div className="flex-1 break-all text-slate-300">
                                        {typeof log.payload === 'string' ? log.payload : JSON.stringify(log.payload)}
                                        {log.correlation_id && (
                                            <span className="ml-2 pl-2 border-l border-slate-700 text-slate-500 text-[10px] cursor-help hover:text-slate-300 transition-colors" title={`Correlation ID: ${log.correlation_id}`}>
                                                ID:{log.correlation_id.slice(0, 8)}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </ScrollArea>
            </div>
        </Card>
    );
}
