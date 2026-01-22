"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Bell, RefreshCw, Database } from "lucide-react";
import { getDataConfig } from "@/lib/api";

interface HeaderProps {
    mode: string;
    agentAvailable: boolean;
}

const dataModeStyles: Record<string, { bg: string; text: string; border: string; pulse?: boolean }> = {
    SAMPLE: { bg: "bg-blue-500/20", text: "text-blue-400", border: "border-blue-500/50" },
    HISTORICAL: { bg: "bg-green-500/20", text: "text-green-400", border: "border-green-500/50" },
    BACKTEST: { bg: "bg-yellow-500/20", text: "text-yellow-400", border: "border-yellow-500/50" },
    LIVE: { bg: "bg-red-500/20", text: "text-red-400", border: "border-red-500/50", pulse: true },
};

export function Header({ mode, agentAvailable }: HeaderProps) {
    const { data: dataConfig } = useQuery({
        queryKey: ["dataConfig"],
        queryFn: getDataConfig,
        staleTime: 30000,
    });

    const dataMode = dataConfig?.data_mode || "SAMPLE";
    const dataModeStyle = dataModeStyles[dataMode] || dataModeStyles.SAMPLE;

    const getModeColor = (mode: string) => {
        switch (mode) {
            case "EXECUTION":
                return "bg-red-500/20 text-red-400 border-red-500/50";
            case "SIMULATION":
                return "bg-yellow-500/20 text-yellow-400 border-yellow-500/50";
            default:
                return "bg-emerald-500/20 text-emerald-400 border-emerald-500/50";
        }
    };

    return (
        <header className="h-16 border-b border-slate-800 bg-slate-950 flex items-center justify-between px-6">
            <div className="flex items-center gap-4">
                <h1 className="text-lg font-semibold text-slate-100">ICT Trading Platform</h1>

                {/* Execution Mode Badge */}
                <Badge variant="outline" className={getModeColor(mode)}>
                    {mode}
                </Badge>

                {/* Data Mode Badge */}
                <Badge
                    variant="outline"
                    className={`${dataModeStyle.bg} ${dataModeStyle.text} ${dataModeStyle.border} flex items-center gap-1.5`}
                >
                    <Database className="w-3 h-3" />
                    {dataMode}
                    {dataModeStyle.pulse && (
                        <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                        </span>
                    )}
                </Badge>

                {/* Agent Status */}
                <div className="flex items-center gap-2">
                    <div
                        className={`w-2 h-2 rounded-full ${agentAvailable ? "bg-emerald-500" : "bg-red-500"
                            }`}
                    />
                    <span className="text-sm text-slate-400">
                        Agent {agentAvailable ? "Online" : "Offline"}
                    </span>
                </div>
            </div>

            <div className="flex items-center gap-2">
                <Button variant="ghost" size="icon" className="text-slate-400 hover:text-slate-100">
                    <RefreshCw className="w-5 h-5" />
                </Button>
                <Button variant="ghost" size="icon" className="text-slate-400 hover:text-slate-100">
                    <Bell className="w-5 h-5" />
                </Button>
            </div>
        </header>
    );
}

