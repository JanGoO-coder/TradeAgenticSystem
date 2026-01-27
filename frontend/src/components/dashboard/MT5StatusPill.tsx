"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getMT5Status, connectMT5, disconnectMT5, MT5Status } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { Loader2, Plug, PlugZap, Unplug } from "lucide-react";

interface MT5StatusPillProps {
    onStatusChange?: (status: MT5Status) => void;
    showConnectButton?: boolean;
    className?: string;
}

export function MT5StatusPill({
    onStatusChange,
    showConnectButton = true,
    className = ""
}: MT5StatusPillProps) {
    const queryClient = useQueryClient();

    // Query MT5 status
    const { data: mt5Status, isLoading, refetch } = useQuery({
        queryKey: ["mt5Status"],
        queryFn: getMT5Status,
        refetchInterval: 10000, // Check every 10 seconds
        staleTime: 5000,
    });

    // Connect mutation
    const connectMutation = useMutation({
        mutationFn: connectMT5,
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["mt5Status"] });
            queryClient.invalidateQueries({ queryKey: ["mt5Symbols"] });
            if (onStatusChange && data.connected) {
                refetch().then((result) => {
                    if (result.data) onStatusChange(result.data);
                });
            }
        },
    });

    // Disconnect mutation
    const disconnectMutation = useMutation({
        mutationFn: disconnectMT5,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["mt5Status"] });
            queryClient.invalidateQueries({ queryKey: ["mt5Symbols"] });
        },
    });

    const isConnecting = connectMutation.isPending;
    const isDisconnecting = disconnectMutation.isPending;
    const isConnected = mt5Status?.connected || false;
    const isAvailable = mt5Status?.available || false;

    // Status pill styling
    const getStatusStyle = () => {
        if (isLoading || isConnecting) {
            return "bg-blue-500/20 text-blue-400 border-blue-500/50";
        }
        if (isConnected) {
            return "bg-emerald-500/20 text-emerald-400 border-emerald-500/50";
        }
        if (isAvailable) {
            return "bg-yellow-500/20 text-yellow-400 border-yellow-500/50";
        }
        return "bg-red-500/20 text-red-400 border-red-500/50";
    };

    // Status text
    const getStatusText = () => {
        if (isLoading) return "Checking...";
        if (isConnecting) return "Connecting...";
        if (isDisconnecting) return "Disconnecting...";
        if (isConnected) return "MT5 Connected";
        if (isAvailable) return "MT5 Available";
        return "MT5 Unavailable";
    };

    // Status icon
    const getStatusIcon = () => {
        if (isLoading || isConnecting || isDisconnecting) {
            return <Loader2 className="w-3 h-3 animate-spin" />;
        }
        if (isConnected) {
            return <PlugZap className="w-3 h-3" />;
        }
        if (isAvailable) {
            return <Plug className="w-3 h-3" />;
        }
        return <Unplug className="w-3 h-3" />;
    };

    return (
        <div className={`flex items-center gap-2 ${className}`}>
            <TooltipProvider>
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Badge
                            variant="outline"
                            className={`${getStatusStyle()} cursor-default transition-all duration-300`}
                        >
                            <span className="flex items-center gap-1.5">
                                {getStatusIcon()}
                                {getStatusText()}
                            </span>
                            {isConnected && (
                                <span className="relative ml-1.5 flex h-2 w-2">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                                </span>
                            )}
                        </Badge>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="bg-slate-900 border-slate-700">
                        {isConnected && mt5Status?.terminal_info ? (
                            <div className="text-xs space-y-1">
                                <div className="font-medium text-slate-100">
                                    {mt5Status.terminal_info.company}
                                </div>
                                <div className="text-slate-400">
                                    {mt5Status.terminal_info.name}
                                </div>
                                <div className="text-slate-500">
                                    Trade: {mt5Status.terminal_info.trade_allowed ? "Allowed" : "Read-only"}
                                </div>
                            </div>
                        ) : isAvailable ? (
                            <p className="text-xs">MT5 package ready. Click Connect to establish connection.</p>
                        ) : (
                            <p className="text-xs">MT5 terminal not detected. Ensure MetaTrader 5 is installed and running.</p>
                        )}
                    </TooltipContent>
                </Tooltip>
            </TooltipProvider>

            {showConnectButton && isAvailable && !isConnected && (
                <Button
                    size="sm"
                    variant="outline"
                    onClick={() => connectMutation.mutate()}
                    disabled={isConnecting}
                    className="h-6 px-2 text-xs border-slate-700 hover:bg-slate-800"
                >
                    {isConnecting ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                        "Connect"
                    )}
                </Button>
            )}

            {showConnectButton && isConnected && (
                <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => disconnectMutation.mutate()}
                    disabled={isDisconnecting}
                    className="h-6 px-2 text-xs text-slate-500 hover:text-slate-300 hover:bg-slate-800"
                >
                    {isDisconnecting ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                        <Unplug className="w-3 h-3" />
                    )}
                </Button>
            )}
        </div>
    );
}
