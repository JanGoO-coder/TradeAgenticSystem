"use client";

import { LLMDecision } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Brain, TrendingUp, TrendingDown, Minus, Target, Shield, AlertTriangle, CheckCircle } from "lucide-react";

interface ReasoningPanelProps {
    decision?: LLMDecision | null;
    className?: string;
}

export function ReasoningPanel({ decision, className }: ReasoningPanelProps) {
    if (!decision) {
        return (
            <Card className={`bg-slate-900 border-slate-800 ${className}`}>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
                        <Brain className="w-4 h-4 text-purple-400" />
                        LLM Reasoning
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="text-sm text-slate-500 text-center py-4">
                        Run an analysis to see LLM reasoning
                    </div>
                </CardContent>
            </Card>
        );
    }

    const getBiasIcon = () => {
        switch (decision.bias) {
            case "BULLISH":
                return <TrendingUp className="w-5 h-5 text-emerald-400" />;
            case "BEARISH":
                return <TrendingDown className="w-5 h-5 text-red-400" />;
            default:
                return <Minus className="w-5 h-5 text-slate-400" />;
        }
    };

    const getBiasColor = () => {
        switch (decision.bias) {
            case "BULLISH":
                return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
            case "BEARISH":
                return "text-red-400 bg-red-500/10 border-red-500/30";
            default:
                return "text-slate-400 bg-slate-500/10 border-slate-500/30";
        }
    };

    const getActionColor = () => {
        switch (decision.action) {
            case "TRADE":
                return "text-emerald-400 bg-emerald-500/20";
            case "MONITOR":
                return "text-amber-400 bg-amber-500/20";
            default:
                return "text-slate-400 bg-slate-500/20";
        }
    };

    const getConfidenceColor = () => {
        if (decision.confidence >= 80) return "text-emerald-400";
        if (decision.confidence >= 60) return "text-amber-400";
        return "text-red-400";
    };

    return (
        <Card className={`bg-slate-900 border-slate-800 ${className}`}>
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
                    <Brain className="w-4 h-4 text-purple-400" />
                    LLM Reasoning
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Main Decision Row */}
                <div className="flex items-center justify-between gap-3">
                    {/* Bias */}
                    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${getBiasColor()}`}>
                        {getBiasIcon()}
                        <span className="font-semibold">{decision.bias}</span>
                    </div>

                    {/* Action */}
                    <div className={`px-3 py-2 rounded-lg font-semibold ${getActionColor()}`}>
                        {decision.action}
                    </div>

                    {/* Confidence */}
                    <div className="text-right">
                        <div className={`text-2xl font-bold ${getConfidenceColor()}`}>
                            {decision.confidence}%
                        </div>
                        <div className="text-xs text-slate-500">Confidence</div>
                    </div>
                </div>

                {/* Assessments */}
                {(decision.structure_assessment || decision.session_assessment) && (
                    <div className="grid grid-cols-2 gap-2">
                        {decision.structure_assessment && (
                            <div className="bg-slate-800/50 rounded-lg p-2">
                                <div className="text-xs text-slate-500 mb-1">Structure</div>
                                <div className="text-sm text-slate-300">{decision.structure_assessment}</div>
                            </div>
                        )}
                        {decision.session_assessment && (
                            <div className="bg-slate-800/50 rounded-lg p-2">
                                <div className="text-xs text-slate-500 mb-1">Session</div>
                                <div className="text-sm text-slate-300">{decision.session_assessment}</div>
                            </div>
                        )}
                    </div>
                )}

                {/* Key Levels */}
                {decision.key_levels && (
                    <div className="bg-slate-800/30 rounded-lg p-3">
                        <div className="flex items-center gap-2 text-xs text-slate-400 mb-2">
                            <Target className="w-3 h-3" />
                            Key Levels
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-center">
                            <div>
                                <div className="text-xs text-slate-500">Entry</div>
                                <div className="text-sm font-mono text-emerald-400">
                                    {decision.key_levels.entry_zone?.toFixed(5) || "—"}
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-slate-500">Stop Loss</div>
                                <div className="text-sm font-mono text-red-400">
                                    {decision.key_levels.stop_loss?.toFixed(5) || "—"}
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-slate-500">Target</div>
                                <div className="text-sm font-mono text-amber-400">
                                    {decision.key_levels.target?.toFixed(5) || "—"}
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Entry Conditions */}
                {decision.entry_conditions_met && decision.entry_conditions_met.length > 0 && (
                    <div>
                        <div className="flex items-center gap-2 text-xs text-slate-400 mb-2">
                            <CheckCircle className="w-3 h-3 text-emerald-400" />
                            Conditions Met
                        </div>
                        <div className="flex flex-wrap gap-1">
                            {decision.entry_conditions_met.map((condition, i) => (
                                <span
                                    key={i}
                                    className="text-xs px-2 py-1 bg-emerald-500/10 text-emerald-400 rounded-md border border-emerald-500/30"
                                >
                                    {condition}
                                </span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Blocking Factors */}
                {decision.blocking_factors && decision.blocking_factors.length > 0 && (
                    <div>
                        <div className="flex items-center gap-2 text-xs text-slate-400 mb-2">
                            <AlertTriangle className="w-3 h-3 text-amber-400" />
                            Blocking Factors
                        </div>
                        <div className="flex flex-wrap gap-1">
                            {decision.blocking_factors.map((factor, i) => (
                                <span
                                    key={i}
                                    className="text-xs px-2 py-1 bg-amber-500/10 text-amber-400 rounded-md border border-amber-500/30"
                                >
                                    {factor}
                                </span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Reasoning */}
                <div className="bg-slate-800/30 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-xs text-slate-400 mb-2">
                        <Shield className="w-3 h-3" />
                        Reasoning
                    </div>
                    <p className="text-sm text-slate-300 leading-relaxed">
                        {decision.reasoning}
                    </p>
                </div>
            </CardContent>
        </Card>
    );
}
