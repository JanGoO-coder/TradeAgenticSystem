"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
    CheckCircle2,
    XCircle,
    AlertTriangle,
    ChevronDown,
    ChevronRight,
    BookOpen
} from "lucide-react";
import { useState } from "react";
import { Checklist } from "@/lib/api";

// Rule definitions from ICT Rulebook
const ruleDefinitions: Record<string, { name: string; description: string; category: string }> = {
    "1.1": { name: "HTF Bias", description: "1H directional bias must be established (HH/HL or LH/LL)", category: "Bias" },
    "1.1.1": { name: "Clean Structure", description: "Trades only allowed when 1H structure is clean and non-overlapping", category: "Bias" },
    "1.2": { name: "LTF Alignment", description: "15M must align with 1H bias direction", category: "Bias" },
    "1.2.1": { name: "External vs Internal", description: "External range (1H) takes precedence over internal (15M)", category: "Bias" },
    "2.1": { name: "Swing Points", description: "Identify swing highs and lows using fractal logic", category: "Structure" },
    "2.3": { name: "Market Structure Shift", description: "Displacement through a prior swing high/low signals shift", category: "Structure" },
    "3.4": { name: "Liquidity Sweep", description: "Price must sweep sell-side (longs) or buy-side (shorts) before entry", category: "Liquidity" },
    "5.1": { name: "Premium/Discount", description: "Longs only in discount (below 50%), shorts only in premium", category: "PD Array" },
    "5.2": { name: "Fair Value Gap", description: "3-candle imbalance creates FVG for potential entry", category: "PD Array" },
    "6.1": { name: "OTE Zone", description: "Entry between 62%-79% retracement of recent impulse", category: "Entry" },
    "6.2": { name: "FVG Entry", description: "Entry at consequent encroachment (50%) of FVG", category: "Entry" },
    "6.5": { name: "ICT 2022 Model", description: "Sweep + displacement + FVG for high-probability entries", category: "Entry" },
    "7.1": { name: "Fixed Risk", description: "Risk 1% of account per trade", category: "Risk" },
    "7.2": { name: "R:R Minimum", description: "Minimum 1:2 risk-reward ratio required", category: "Risk" },
    "8.1": { name: "Kill Zones", description: "Trade only during London (2-5 AM EST) or NY (7-10 AM EST)", category: "Session" },
    "8.4": { name: "News Rules", description: "No entries within 30min of high-impact news", category: "Session" },
};

interface RuleExplanationPanelProps {
    checklist: Checklist | null;
    ruleRefs: string[];
    explanation: string;
}

interface RuleItemProps {
    ruleId: string;
    passed: boolean;
    isExpanded: boolean;
    onToggle: () => void;
}

function RuleItem({ ruleId, passed, isExpanded, onToggle }: RuleItemProps) {
    const rule = ruleDefinitions[ruleId];

    if (!rule) {
        return (
            <div className="p-2 bg-slate-800/50 rounded text-sm text-slate-500">
                Rule {ruleId}
            </div>
        );
    }

    return (
        <div className="bg-slate-800/50 rounded-lg overflow-hidden">
            <button
                onClick={onToggle}
                className="w-full flex items-center gap-3 p-3 hover:bg-slate-800 transition-colors"
            >
                {passed ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                ) : (
                    <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                )}

                <div className="flex-1 text-left">
                    <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-100">{rule.name}</span>
                        <Badge variant="outline" className="text-xs text-slate-500">
                            {ruleId}
                        </Badge>
                    </div>
                </div>

                {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-slate-500" />
                ) : (
                    <ChevronRight className="w-4 h-4 text-slate-500" />
                )}
            </button>

            {isExpanded && (
                <div className="px-3 pb-3 pt-0">
                    <div className="pl-8 space-y-2">
                        <p className="text-sm text-slate-400">{rule.description}</p>
                        <Badge variant="outline" className="text-xs">
                            {rule.category}
                        </Badge>
                    </div>
                </div>
            )}
        </div>
    );
}

export function RuleExplanationPanel({ checklist, ruleRefs, explanation }: RuleExplanationPanelProps) {
    const [expandedRules, setExpandedRules] = useState<Set<string>>(new Set());

    const toggleRule = (ruleId: string) => {
        setExpandedRules((prev) => {
            const next = new Set(prev);
            if (next.has(ruleId)) {
                next.delete(ruleId);
            } else {
                next.add(ruleId);
            }
            return next;
        });
    };

    // Map checklist items to rules
    const checklistToRules: Record<keyof Checklist, string> = {
        htf_bias_exists: "1.1",
        ltf_mss: "1.2",
        pd_alignment: "5.1",
        liquidity_sweep_detected: "3.4",
        session_ok: "8.1",
        news_ok: "8.4",
        rr_minimum_met: "7.2",
    };

    return (
        <Card className="bg-slate-900 border-slate-800">
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
                        <BookOpen className="w-4 h-4" />
                        Rule Explanation
                    </CardTitle>
                    {checklist && (
                        <Badge variant="outline" className="text-xs">
                            {Object.values(checklist).filter(Boolean).length}/7 Passed
                        </Badge>
                    )}
                </div>
            </CardHeader>
            <CardContent>
                <div className="h-[350px] pr-4 overflow-y-auto">
                    <div className="space-y-2">
                        {/* Explanation Summary */}
                        {explanation && (
                            <div className="p-3 bg-slate-800/30 rounded-lg border border-slate-700 mb-4">
                                <p className="text-sm text-slate-300 leading-relaxed">{explanation}</p>
                            </div>
                        )}

                        <Separator className="bg-slate-800 my-4" />

                        {/* Checklist Rules */}
                        <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">
                            Checklist Rules
                        </div>
                        {checklist && Object.entries(checklistToRules).map(([key, ruleId]) => (
                            <RuleItem
                                key={key}
                                ruleId={ruleId}
                                passed={checklist[key as keyof Checklist]}
                                isExpanded={expandedRules.has(ruleId)}
                                onToggle={() => toggleRule(ruleId)}
                            />
                        ))}

                        {/* Setup-Specific Rules */}
                        {ruleRefs.length > 0 && (
                            <>
                                <Separator className="bg-slate-800 my-4" />
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">
                                    Setup Rules
                                </div>
                                {ruleRefs
                                    .filter((r) => !Object.values(checklistToRules).includes(r))
                                    .map((ruleId) => (
                                        <RuleItem
                                            key={ruleId}
                                            ruleId={ruleId}
                                            passed={true}
                                            isExpanded={expandedRules.has(ruleId)}
                                            onToggle={() => toggleRule(ruleId)}
                                        />
                                    ))}
                            </>
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
