"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { TradeSetupResponse } from "@/lib/api";
import {
    TrendingUp,
    TrendingDown,
    Minus,
    Target,
    ShieldAlert,
    CheckCircle2,
    XCircle,
    AlertCircle,
    Crosshair,
    Scale,
    ListChecks,
    Brain,
    Gauge,
    Zap,
} from "lucide-react";

interface BacktestAnalysisPanelProps {
    analysis: TradeSetupResponse | null;
    className?: string;
    onExecuteTrade?: () => void;
}

// Checklist item component
function ChecklistItem({
    label,
    passed,
    ruleRef
}: {
    label: string;
    passed: boolean;
    ruleRef?: string;
}) {
    return (
        <div className="flex items-center justify-between py-1">
            <div className="flex items-center gap-2">
                {passed ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                    <XCircle className="w-3.5 h-3.5 text-red-400" />
                )}
                <span className={`text-xs ${passed ? 'text-slate-300' : 'text-slate-500'}`}>
                    {label}
                </span>
            </div>
            {ruleRef && (
                <span className="text-[10px] text-slate-600">{ruleRef}</span>
            )}
        </div>
    );
}

// Stat box component
function StatBox({
    label,
    value,
    valueColor = "text-slate-100",
    small = false
}: {
    label: string;
    value: string | number;
    valueColor?: string;
    small?: boolean;
}) {
    return (
        <div className={`bg-slate-800/50 rounded p-2 ${small ? 'p-1.5' : ''}`}>
            <div className="text-[10px] text-slate-500 uppercase">{label}</div>
            <div className={`${small ? 'text-sm' : 'text-base'} font-mono ${valueColor}`}>
                {value}
            </div>
        </div>
    );
}

export function BacktestAnalysisPanel({ analysis, className = "", onExecuteTrade }: BacktestAnalysisPanelProps) {
    if (!analysis) {
        return (
            <Card className={`bg-slate-900 border-slate-800 ${className}`}>
                <CardContent className="flex items-center justify-center h-full min-h-[200px]">
                    <div className="text-center text-slate-500">
                        <Brain className="w-10 h-10 mx-auto mb-2 opacity-50" />
                        <p className="text-sm">Step through data to see analysis</p>
                    </div>
                </CardContent>
            </Card>
        );
    }

    // Destructure with safe defaults for all fields
    const status = analysis.status || 'WAIT';
    const reason_short = analysis.reason_short || 'Analyzing...';
    const confidence = analysis.confidence ?? 0;
    const explanation = analysis.explanation || 'No explanation available';

    // Safe defaults for complex objects
    const htf_bias = analysis.htf_bias || { value: 'NEUTRAL' as const, rule_refs: [] };
    const setup = analysis.setup || {
        name: 'NO_SETUP',
        type: null,
        entry_price: null,
        stop_loss: null,
        take_profit: null,
        confluence_score: 0,
        rule_refs: []
    };
    const risk = analysis.risk || {
        account_balance: 10000,
        risk_pct: 1.0,
        position_size: 0,
        rr: null
    };
    const checklist = analysis.checklist || {
        htf_bias_exists: false,
        ltf_mss: false,
        pd_alignment: false,
        liquidity_sweep_detected: false,
        session_ok: false,
        news_ok: false,
        rr_minimum_met: false
    };

    // Status styling
    const statusStyles: Record<string, string> = {
        TRADE_NOW: "bg-emerald-500/20 text-emerald-400 border-emerald-500/50",
        WAIT: "bg-yellow-500/20 text-yellow-400 border-yellow-500/50",
        NO_TRADE: "bg-slate-500/20 text-slate-400 border-slate-500/50",
    };

    // Bias styling
    const biasStyles: Record<string, { bg: string; text: string; icon: typeof TrendingUp }> = {
        BULLISH: { bg: "bg-emerald-500/10", text: "text-emerald-400", icon: TrendingUp },
        BEARISH: { bg: "bg-red-500/10", text: "text-red-400", icon: TrendingDown },
        NEUTRAL: { bg: "bg-slate-500/10", text: "text-slate-400", icon: Minus },
    };

    // Safe bias value access
    const biasValue = htf_bias.value || 'NEUTRAL';
    const biasStyle = biasStyles[biasValue] || biasStyles.NEUTRAL;
    const BiasIcon = biasStyle.icon;

    // Calculate checklist score
    const checklistItems = [
        { key: 'htf_bias_exists', label: 'HTF Bias', ref: '1.1' },
        { key: 'ltf_mss', label: 'LTF MSS', ref: '3.4' },
        { key: 'pd_alignment', label: 'PD Alignment', ref: '2.2' },
        { key: 'liquidity_sweep_detected', label: 'Liquidity Sweep', ref: '2.4' },
        { key: 'session_ok', label: 'Session OK', ref: '4.1' },
        { key: 'news_ok', label: 'News Clear', ref: '4.3' },
        { key: 'rr_minimum_met', label: 'R:R Met', ref: '5.1' },
    ];

    const passedCount = checklistItems.filter(
        item => checklist[item.key as keyof typeof checklist]
    ).length;

    return (
        <div className={`h-full overflow-y-auto ${className}`}>
            <div className="space-y-3 p-1">
                {/* Status & Confidence Row */}
                <Card className="bg-slate-900 border-slate-800">
                    <CardContent className="p-3">
                        <div className="flex items-center justify-between mb-2">
                            <Badge variant="outline" className={statusStyles[status]}>
                                {status === "TRADE_NOW" && <Target className="w-3 h-3 mr-1" />}
                                {status === "WAIT" && <AlertCircle className="w-3 h-3 mr-1" />}
                                {status === "NO_TRADE" && <ShieldAlert className="w-3 h-3 mr-1" />}
                                {status.replace("_", " ")}
                            </Badge>
                            <div className="flex items-center gap-2">
                                <Gauge className="w-3.5 h-3.5 text-slate-500" />
                                <span className={`text-sm font-medium ${confidence >= 70 ? 'text-emerald-400' :
                                    confidence >= 50 ? 'text-yellow-400' : 'text-slate-400'
                                    }`}>
                                    {confidence}%
                                </span>
                            </div>
                        </div>
                        <p className="text-xs text-slate-400">{reason_short}</p>
                    </CardContent>
                </Card>

                {/* HTF Bias */}
                <Card className="bg-slate-900 border-slate-800">
                    <CardHeader className="pb-2 pt-3 px-3">
                        <CardTitle className="text-xs font-medium text-slate-500 flex items-center gap-2">
                            <TrendingUp className="w-3.5 h-3.5" />
                            HTF BIAS
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="px-3 pb-3">
                        <div className={`flex items-center gap-2 p-2 rounded ${biasStyle.bg}`}>
                            <BiasIcon className={`w-5 h-5 ${biasStyle.text}`} />
                            <span className={`font-semibold ${biasStyle.text}`}>
                                {biasValue}
                            </span>
                        </div>
                    </CardContent>
                </Card>

                {/* Setup Details */}
                {setup.name !== "NO_SETUP" && (
                    <Card className="bg-slate-900 border-slate-800">
                        <CardHeader className="pb-2 pt-3 px-3">
                            <CardTitle className="text-xs font-medium text-slate-500 flex items-center gap-2">
                                <Crosshair className="w-3.5 h-3.5" />
                                SETUP: {setup.name}
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="px-3 pb-3 space-y-2">
                            <div className="grid grid-cols-3 gap-2">
                                <StatBox
                                    label="Entry"
                                    value={setup.entry_price?.toFixed(5) || "--"}
                                    valueColor="text-blue-400"
                                    small
                                />
                                <StatBox
                                    label="Stop"
                                    value={setup.stop_loss?.toFixed(5) || "--"}
                                    valueColor="text-red-400"
                                    small
                                />
                                <StatBox
                                    label="Target"
                                    value={setup.take_profit?.[0]?.toFixed(5) || "--"}
                                    valueColor="text-emerald-400"
                                    small
                                />
                            </div>
                            <div className="flex items-center justify-between text-xs">
                                <span className="text-slate-500">Confluence</span>
                                <div className="flex items-center gap-2">
                                    <div className="w-20 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                        <div
                                            className={`h-full rounded-full ${setup.confluence_score >= 8 ? 'bg-emerald-500' :
                                                setup.confluence_score >= 5 ? 'bg-yellow-500' : 'bg-red-500'
                                                }`}
                                            style={{ width: `${(setup.confluence_score / 10) * 100}%` }}
                                        />
                                    </div>
                                    <span className="text-slate-300 font-mono">{setup.confluence_score}/10</span>
                                </div>
                            </div>

                            {/* Execute Trade Button */}
                            {status === "TRADE_NOW" && onExecuteTrade && (
                                <Button
                                    className="w-full mt-2"
                                    variant={setup.type === 'LONG' ? 'default' : 'destructive'}
                                    size="sm"
                                    onClick={onExecuteTrade}
                                >
                                    <Zap className="w-3.5 h-3.5 mr-1.5" />
                                    Execute {setup.type} Trade
                                </Button>
                            )}
                        </CardContent>
                    </Card>
                )}

                {/* Risk Parameters */}
                <Card className="bg-slate-900 border-slate-800">
                    <CardHeader className="pb-2 pt-3 px-3">
                        <CardTitle className="text-xs font-medium text-slate-500 flex items-center gap-2">
                            <Scale className="w-3.5 h-3.5" />
                            RISK
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="px-3 pb-3">
                        <div className="grid grid-cols-2 gap-2">
                            <StatBox
                                label="Position"
                                value={risk.position_size.toFixed(2)}
                                small
                            />
                            <StatBox
                                label="R:R"
                                value={risk.rr?.toFixed(1) || "--"}
                                valueColor={risk.rr && risk.rr >= 2 ? "text-emerald-400" : "text-yellow-400"}
                                small
                            />
                        </div>
                    </CardContent>
                </Card>

                {/* Checklist */}
                <Card className="bg-slate-900 border-slate-800">
                    <CardHeader className="pb-2 pt-3 px-3">
                        <CardTitle className="text-xs font-medium text-slate-500 flex items-center justify-between">
                            <span className="flex items-center gap-2">
                                <ListChecks className="w-3.5 h-3.5" />
                                CHECKLIST
                            </span>
                            <span className={`font-mono ${passedCount >= 6 ? 'text-emerald-400' :
                                passedCount >= 4 ? 'text-yellow-400' : 'text-red-400'
                                }`}>
                                {passedCount}/{checklistItems.length}
                            </span>
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="px-3 pb-3">
                        <div className="space-y-0.5">
                            {checklistItems.map(item => (
                                <ChecklistItem
                                    key={item.key}
                                    label={item.label}
                                    passed={checklist[item.key as keyof typeof checklist]}
                                    ruleRef={item.ref}
                                />
                            ))}
                        </div>
                    </CardContent>
                </Card>

                {/* Explanation */}
                <Card className="bg-slate-900 border-slate-800">
                    <CardHeader className="pb-2 pt-3 px-3">
                        <CardTitle className="text-xs font-medium text-slate-500 flex items-center gap-2">
                            <Brain className="w-3.5 h-3.5" />
                            AI ANALYSIS
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="px-3 pb-3">
                        <p className="text-xs text-slate-400 leading-relaxed">
                            {explanation}
                        </p>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
