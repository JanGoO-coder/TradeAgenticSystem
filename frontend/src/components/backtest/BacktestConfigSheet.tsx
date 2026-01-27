"use client";

import { useState, useEffect } from "react";
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
import { Switch } from "@/components/ui/switch";
import { TradingPairSelector } from "@/components/dashboard/TradingPairSelector";
import { Separator } from "@/components/ui/separator";
import {
    Calendar, Save, Zap, Bot, HardDrive,
    FolderOpen, Trash2, Info
} from "lucide-react";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

interface BacktestConfig {
    symbol: string;
    fromDate: string;
    toDate: string;
    timeframes: string[];
    tickMode?: boolean;
    agentAutoExecute?: boolean;
    // Extended fields for unified session API
    initialBalance?: number;
    riskPerTrade?: number;
}

interface SavedSession {
    filename: string;
    filepath: string;
    saved_at: string;
    symbol: string;
    trades_count: number;
    final_balance: number;
    progress_pct: number;
}

interface BacktestConfigSheetProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    config: BacktestConfig;
    onConfigChange: (config: BacktestConfig) => void;
    onApply: () => void;
    mt5Symbols?: string[];
    onSaveSession?: () => void;
    onLoadSession?: (filepath: string) => void;
}

export function BacktestConfigSheet({
    open,
    onOpenChange,
    config,
    onConfigChange,
    onApply,
    mt5Symbols,
    onSaveSession,
    onLoadSession,
}: BacktestConfigSheetProps) {
    const [savedSessions, setSavedSessions] = useState<SavedSession[]>([]);
    const [selectedSession, setSelectedSession] = useState<string>("");
    const [loadingModes, setLoadingModes] = useState(false);

    const updateConfig = (partial: Partial<BacktestConfig>) => {
        onConfigChange({ ...config, ...partial });
    };

    // Fetch saved sessions when sheet opens
    useEffect(() => {
        if (open) {
            fetchSavedSessions();
            fetchModeSettings();
        }
    }, [open]);

    const fetchSavedSessions = async () => {
        // Note: Session persistence is not yet implemented in the unified session API
        // The deprecated /api/v1/backtest/sessions endpoint no longer exists
        setSavedSessions([]);
    };

    const fetchModeSettings = async () => {
        // Note: These settings are now local-only until backend session API supports them
        // The deprecated /api/v1/backtest/mode-settings endpoint no longer exists
        setLoadingModes(false);
    };

    const handleTickModeChange = (enabled: boolean) => {
        // Update local state only - tick mode will be applied when session is initialized
        updateConfig({ tickMode: enabled });
    };

    const handleAgentAutoExecuteChange = (enabled: boolean) => {
        // Update local state only - agent auto-execute will be applied when session is initialized
        updateConfig({ agentAutoExecute: enabled });
    };

    const handleLoadSession = () => {
        if (selectedSession && onLoadSession) {
            onLoadSession(selectedSession);
            onOpenChange(false);
        }
    };

    const handleDeleteSession = async (filepath: string) => {
        // Note: Session persistence is not yet implemented in the unified session API
        console.log("Session delete not implemented:", filepath);
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
            <SheetContent className="bg-slate-900 border-slate-800 w-[380px] overflow-y-auto">
                <SheetHeader>
                    <SheetTitle className="text-slate-100 flex items-center gap-2">
                        <Calendar className="w-5 h-5 text-blue-400" />
                        Backtest Configuration
                    </SheetTitle>
                    <SheetDescription className="text-slate-400">
                        Configure the backtest parameters and simulation modes
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
                                    className={`h-7 text-xs ${config.timeframes.includes(tf)
                                        ? "bg-blue-600 border-blue-500 text-white hover:bg-blue-700"
                                        : "border-slate-700"
                                        }`}
                                >
                                    {tf}
                                </Button>
                            ))}
                        </div>
                    </div>

                    <Separator className="bg-slate-800" />

                    {/* Simulation Mode Settings */}
                    <div className="space-y-4">
                        <Label className="text-sm text-slate-300">Simulation Settings</Label>

                        {/* Tick Mode Toggle */}
                        <div className="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 border border-slate-700">
                            <div className="flex items-center gap-3">
                                <Zap className="w-4 h-4 text-yellow-400" />
                                <div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm text-slate-200">Tick Mode</span>
                                        <TooltipProvider>
                                            <Tooltip>
                                                <TooltipTrigger>
                                                    <Info className="w-3 h-3 text-slate-500" />
                                                </TooltipTrigger>
                                                <TooltipContent className="max-w-[250px]">
                                                    <p>Replay actual tick data within each bar for accurate TP/SL hit detection order. Uses ~50MB RAM.</p>
                                                </TooltipContent>
                                            </Tooltip>
                                        </TooltipProvider>
                                    </div>
                                    <span className="text-xs text-slate-500">Accurate TP/SL timing</span>
                                </div>
                            </div>
                            <Switch
                                checked={config.tickMode || false}
                                onCheckedChange={handleTickModeChange}
                                disabled={loadingModes}
                            />
                        </div>

                        {/* Agent Auto-Execute Toggle */}
                        <div className="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 border border-slate-700">
                            <div className="flex items-center gap-3">
                                <Bot className="w-4 h-4 text-purple-400" />
                                <div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm text-slate-200">Agent Auto-Execute</span>
                                        <TooltipProvider>
                                            <Tooltip>
                                                <TooltipTrigger>
                                                    <Info className="w-3 h-3 text-slate-500" />
                                                </TooltipTrigger>
                                                <TooltipContent className="max-w-[250px]">
                                                    <p>Agent automatically places trades when valid setup is detected at bar close.</p>
                                                </TooltipContent>
                                            </Tooltip>
                                        </TooltipProvider>
                                    </div>
                                    <span className="text-xs text-slate-500">Auto-trade on signals</span>
                                </div>
                            </div>
                            <Switch
                                checked={config.agentAutoExecute || false}
                                onCheckedChange={handleAgentAutoExecuteChange}
                                disabled={loadingModes}
                            />
                        </div>
                    </div>

                    <Separator className="bg-slate-800" />

                    {/* Session Management */}
                    <div className="space-y-3">
                        <Label className="text-sm text-slate-300 flex items-center gap-2">
                            <HardDrive className="w-4 h-4" />
                            Session Management
                        </Label>

                        {/* Save Session Button */}
                        {onSaveSession && (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={onSaveSession}
                                className="w-full border-slate-700 h-9"
                            >
                                <Save className="w-4 h-4 mr-2" />
                                Save Current Session
                            </Button>
                        )}

                        {/* Load Session */}
                        {savedSessions.length > 0 && (
                            <div className="space-y-2">
                                <Select value={selectedSession} onValueChange={setSelectedSession}>
                                    <SelectTrigger className="bg-slate-800 border-slate-700 h-9">
                                        <SelectValue placeholder="Load saved session..." />
                                    </SelectTrigger>
                                    <SelectContent className="bg-slate-800 border-slate-700">
                                        {savedSessions.map((session) => (
                                            <SelectItem
                                                key={session.filepath}
                                                value={session.filepath}
                                                className="text-slate-200"
                                            >
                                                <div className="flex flex-col">
                                                    <span className="text-sm">{session.symbol} - {session.trades_count} trades</span>
                                                    <span className="text-xs text-slate-500">
                                                        ${session.final_balance?.toFixed(2)} | {session.progress_pct?.toFixed(0)}% complete
                                                    </span>
                                                </div>
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>

                                <div className="flex gap-2">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleLoadSession}
                                        disabled={!selectedSession}
                                        className="flex-1 border-slate-700 h-8"
                                    >
                                        <FolderOpen className="w-3 h-3 mr-1" />
                                        Load
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => selectedSession && handleDeleteSession(selectedSession)}
                                        disabled={!selectedSession}
                                        className="border-red-800 text-red-400 hover:bg-red-900/30 h-8"
                                    >
                                        <Trash2 className="w-3 h-3" />
                                    </Button>
                                </div>
                            </div>
                        )}
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
