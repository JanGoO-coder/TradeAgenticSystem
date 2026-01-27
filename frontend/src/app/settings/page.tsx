"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getHealth, getMode, setMode, getDataConfig, updateDataConfig, getDataModes, DataConfig } from "@/lib/api";
import {
    Settings as SettingsIcon,
    Shield,
    AlertTriangle,
    CheckCircle2,
    Loader2,
    ArrowRight,
    Database,
    Save
} from "lucide-react";

const modes = [
    {
        value: "ANALYSIS_ONLY",
        label: "Analysis Only",
        description: "View trade analysis and recommendations without any execution",
        color: "bg-blue-500",
        icon: "📊",
        safe: true
    },
    {
        value: "SIMULATION",
        label: "Simulation",
        description: "Paper trading mode - track hypothetical trades without real money",
        color: "bg-emerald-500",
        icon: "📝",
        safe: true
    },
    {
        value: "APPROVAL_REQUIRED",
        label: "Approval Required",
        description: "Manual approval required for each trade before execution",
        color: "bg-yellow-500",
        icon: "✋",
        safe: false
    },
    {
        value: "EXECUTION",
        label: "Live Execution",
        description: "Real trading with actual money - USE WITH CAUTION",
        color: "bg-red-500",
        icon: "⚡",
        safe: false
    }
];

const refreshIntervalOptions = [
    { value: 30, label: "30 seconds" },
    { value: 60, label: "1 minute" },
    { value: 120, label: "2 minutes" },
    { value: 300, label: "5 minutes" },
];

export default function SettingsPage() {
    const queryClient = useQueryClient();

    // Data config form state
    const [dataConfigForm, setDataConfigForm] = useState<DataConfig | null>(null);
    const [hasDataChanges, setHasDataChanges] = useState(false);

    const { data: health } = useQuery({
        queryKey: ["health"],
        queryFn: getHealth,
    });

    const { data: modeData, isLoading: modeLoading } = useQuery({
        queryKey: ["mode"],
        queryFn: getMode,
    });

    const { data: dataConfig, isLoading: dataConfigLoading } = useQuery({
        queryKey: ["dataConfig"],
        queryFn: getDataConfig,
    });

    const { data: dataModes } = useQuery({
        queryKey: ["dataModes"],
        queryFn: getDataModes,
    });

    // Initialize form state when data loads
    useEffect(() => {
        if (dataConfig && !dataConfigForm) {
            setDataConfigForm(dataConfig);
        }
    }, [dataConfig, dataConfigForm]);

    const modeMutation = useMutation({
        mutationFn: setMode,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["mode"] });
            queryClient.invalidateQueries({ queryKey: ["health"] });
        },
    });

    const dataConfigMutation = useMutation({
        mutationFn: updateDataConfig,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["dataConfig"] });
            setHasDataChanges(false);
        },
    });

    const handleDataConfigChange = (field: keyof DataConfig, value: number | string) => {
        if (!dataConfigForm) return;
        setDataConfigForm({ ...dataConfigForm, [field]: value });
        setHasDataChanges(true);
    };

    const handleSaveDataConfig = () => {
        if (dataConfigForm) {
            dataConfigMutation.mutate(dataConfigForm);
        }
    };

    const currentModeIndex = modes.findIndex(m => m.value === modeData?.mode);

    return (
        <div className="flex flex-col h-full w-full overflow-hidden">
            <Header
                mode={health?.mode || "ANALYSIS_ONLY"}
                agentAvailable={health?.agent_available || false}
            />

            <div className="flex-1 overflow-y-auto">
                <div className="p-4 min-w-0">
                    <div className="flex items-center gap-3 mb-4">
                        <SettingsIcon className="w-5 h-5 text-slate-400" />
                        <h2 className="text-lg font-semibold text-slate-100">Settings</h2>
                    </div>

                    {/* Execution Mode */}
                    <Card className="bg-slate-900 border-slate-800 mb-4">
                        <CardHeader className="pb-3">
                            <div className="flex items-center gap-2">
                                <Shield className="w-5 h-5 text-emerald-400" />
                                <CardTitle className="text-base">Execution Mode</CardTitle>
                            </div>
                            <CardDescription className="text-sm">
                                Control how the trading agent executes recommendations
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {modeLoading ? (
                                <div className="flex items-center justify-center py-8">
                                    <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {/* Mode Options */}
                                    <div className="grid gap-2">
                                        {modes.map((mode, index) => {
                                            const isActive = mode.value === modeData?.mode;
                                            const isBlocked = mode.value === "EXECUTION" && modeData?.mode === "ANALYSIS_ONLY";
                                            const isPast = index < currentModeIndex;

                                            return (
                                                <button
                                                    key={mode.value}
                                                    onClick={() => !isBlocked && modeMutation.mutate(mode.value)}
                                                    disabled={isBlocked || modeMutation.isPending}
                                                    className={`relative flex items-center gap-3 p-3 rounded-lg border transition-all text-left ${isActive
                                                        ? "bg-slate-800 border-emerald-500/50"
                                                        : isBlocked
                                                            ? "bg-slate-900/50 border-slate-800 opacity-50 cursor-not-allowed"
                                                            : "bg-slate-900 border-slate-800 hover:border-slate-700 hover:bg-slate-800/50"
                                                        }`}
                                                >
                                                    {/* Status Icon */}
                                                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${isActive ? mode.color : "bg-slate-800"
                                                        }`}>
                                                        <span className="text-lg">{mode.icon}</span>
                                                    </div>

                                                    {/* Content */}
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2 flex-wrap">
                                                            <span className={`font-medium text-sm ${isActive ? "text-slate-100" : "text-slate-300"}`}>
                                                                {mode.label}
                                                            </span>
                                                            {isActive && (
                                                                <Badge className="bg-emerald-500/20 text-emerald-400 text-xs">
                                                                    Active
                                                                </Badge>
                                                            )}
                                                            {!mode.safe && (
                                                                <AlertTriangle className="w-3.5 h-3.5 text-yellow-500" />
                                                            )}
                                                        </div>
                                                        <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">{mode.description}</p>
                                                    </div>

                                                    {/* Active indicator */}
                                                    {isActive && (
                                                        <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                                                    )}

                                                    {/* Arrow for progression */}
                                                    {isPast && !isActive && (
                                                        <ArrowRight className="w-4 h-4 text-slate-600 flex-shrink-0" />
                                                    )}
                                                </button>
                                            );
                                        })}
                                    </div>

                                    {/* Warning */}
                                    {modeData?.mode !== "ANALYSIS_ONLY" && (
                                        <div className="flex items-start gap-2 p-2.5 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                                            <AlertTriangle className="w-4 h-4 text-yellow-500 flex-shrink-0 mt-0.5" />
                                            <div className="text-xs">
                                                <p className="text-yellow-400 font-medium">Execution Mode Active</p>
                                                <p className="text-slate-400 mt-0.5">
                                                    {modeData?.mode === "SIMULATION"
                                                        ? "Paper trades will be recorded for tracking purposes."
                                                        : "Be careful - actions in this mode may affect real positions."}
                                                </p>
                                            </div>
                                        </div>
                                    )}

                                    <Separator className="bg-slate-800" />

                                    {/* Quick Actions */}
                                    <div className="flex gap-2">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="border-slate-700"
                                            onClick={() => modeMutation.mutate("ANALYSIS_ONLY")}
                                            disabled={modeData?.mode === "ANALYSIS_ONLY" || modeMutation.isPending}
                                        >
                                            Reset to Safe Mode
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Data Settings */}
                    <Card className="bg-slate-900 border-slate-800 mb-4">
                        <CardHeader className="pb-3">
                            <div className="flex items-center gap-2">
                                <Database className="w-5 h-5 text-blue-400" />
                                <CardTitle className="text-base">Data Settings</CardTitle>
                            </div>
                            <CardDescription className="text-sm">
                                Configure data source and sampling parameters
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {dataConfigLoading || !dataConfigForm ? (
                                <div className="flex items-center justify-center py-8">
                                    <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {/* Data Mode Selector */}
                                    <div className="space-y-2">
                                        <Label className="text-sm text-slate-300">Data Mode</Label>
                                        <Select
                                            value={dataConfigForm.data_mode}
                                            onValueChange={(value) => handleDataConfigChange("data_mode", value)}
                                        >
                                            <SelectTrigger className="bg-slate-800 border-slate-700">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {dataModes?.modes.map((mode) => (
                                                    <SelectItem key={mode.value} value={mode.value}>
                                                        <div className="flex flex-col">
                                                            <span>{mode.label}</span>
                                                        </div>
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <Separator className="bg-slate-800" />

                                    {/* Bar Counts */}
                                    <div className="grid grid-cols-3 gap-3">
                                        <div className="space-y-2">
                                            <Label className="text-xs text-slate-400">1H Bars</Label>
                                            <Input
                                                type="number"
                                                min={10}
                                                max={500}
                                                value={dataConfigForm.htf_bars}
                                                onChange={(e) => handleDataConfigChange("htf_bars", parseInt(e.target.value) || 50)}
                                                className="bg-slate-800 border-slate-700"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label className="text-xs text-slate-400">15M Bars</Label>
                                            <Input
                                                type="number"
                                                min={10}
                                                max={500}
                                                value={dataConfigForm.ltf_bars}
                                                onChange={(e) => handleDataConfigChange("ltf_bars", parseInt(e.target.value) || 100)}
                                                className="bg-slate-800 border-slate-700"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label className="text-xs text-slate-400">5M Bars</Label>
                                            <Input
                                                type="number"
                                                min={10}
                                                max={500}
                                                value={dataConfigForm.micro_bars}
                                                onChange={(e) => handleDataConfigChange("micro_bars", parseInt(e.target.value) || 50)}
                                                className="bg-slate-800 border-slate-700"
                                            />
                                        </div>
                                    </div>

                                    {/* Refresh Interval */}
                                    <div className="space-y-2">
                                        <Label className="text-sm text-slate-300">Live Refresh Interval</Label>
                                        <Select
                                            value={String(dataConfigForm.live_refresh_interval)}
                                            onValueChange={(value) => handleDataConfigChange("live_refresh_interval", parseInt(value))}
                                        >
                                            <SelectTrigger className="bg-slate-800 border-slate-700">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {refreshIntervalOptions.map((opt) => (
                                                    <SelectItem key={opt.value} value={String(opt.value)}>
                                                        {opt.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    {/* Save Button */}
                                    <div className="flex justify-end">
                                        <Button
                                            onClick={handleSaveDataConfig}
                                            disabled={!hasDataChanges || dataConfigMutation.isPending}
                                            className="bg-blue-600 hover:bg-blue-700"
                                            size="sm"
                                        >
                                            {dataConfigMutation.isPending ? (
                                                <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Saving...</>
                                            ) : (
                                                <><Save className="w-4 h-4 mr-2" />Save Changes</>
                                            )}
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Risk Settings */}
                    <Card className="bg-slate-900 border-slate-800">
                        <CardHeader className="pb-3">
                            <CardTitle className="text-base">Risk Settings</CardTitle>
                            <CardDescription className="text-sm">
                                Configure risk parameters for trade analysis
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                <div className="bg-slate-800 rounded-lg p-3">
                                    <div className="text-xs text-slate-400">Risk Per Trade</div>
                                    <div className="text-xl font-bold text-slate-100">1.0%</div>
                                </div>
                                <div className="bg-slate-800 rounded-lg p-3">
                                    <div className="text-xs text-slate-400">Min R:R Ratio</div>
                                    <div className="text-xl font-bold text-slate-100">1:2</div>
                                </div>
                                <div className="bg-slate-800 rounded-lg p-3">
                                    <div className="text-xs text-slate-400">Max Trades/Session</div>
                                    <div className="text-xl font-bold text-slate-100">3</div>
                                </div>
                                <div className="bg-slate-800 rounded-lg p-3">
                                    <div className="text-xs text-slate-400">Account Balance</div>
                                    <div className="text-xl font-bold text-emerald-400">$10,000</div>
                                </div>
                            </div>
                            <p className="text-xs text-slate-500 mt-3">
                                Risk settings can be configured in the backend .env file
                            </p>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}
