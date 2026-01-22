"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle2, XCircle, Circle } from "lucide-react";
import { Checklist } from "@/lib/api";

interface ChecklistPanelProps {
    checklist: Checklist | null;
}

const checklistItems = [
    { key: "htf_bias_exists", label: "HTF Bias Exists", rule: "1.1" },
    { key: "ltf_mss", label: "LTF MSS/Alignment", rule: "1.2" },
    { key: "pd_alignment", label: "PD Array Alignment", rule: "5.1" },
    { key: "liquidity_sweep_detected", label: "Liquidity Sweep", rule: "3.4" },
    { key: "session_ok", label: "Kill Zone Active", rule: "8.1" },
    { key: "news_ok", label: "News Clear", rule: "8.4" },
    { key: "rr_minimum_met", label: "R:R ≥ 1:2", rule: "7.2" },
];

export function ChecklistPanel({ checklist }: ChecklistPanelProps) {
    if (!checklist) {
        return (
            <Card className="bg-slate-900 border-slate-800">
                <CardHeader>
                    <CardTitle className="text-sm font-medium text-slate-400">
                        Execution Checklist
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="space-y-2">
                        {checklistItems.map((item) => (
                            <div
                                key={item.key}
                                className="flex items-center justify-between py-1 text-sm"
                            >
                                <div className="flex items-center gap-2">
                                    <Circle className="w-4 h-4 text-slate-600" />
                                    <span className="text-slate-500">{item.label}</span>
                                </div>
                                <span className="text-xs text-slate-600">{item.rule}</span>
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>
        );
    }

    const passedCount = Object.values(checklist).filter(Boolean).length;
    const totalCount = Object.keys(checklist).length;

    return (
        <Card className="bg-slate-900 border-slate-800">
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium text-slate-400">
                        Execution Checklist
                    </CardTitle>
                    <span className="text-sm text-emerald-400 font-semibold">
                        {passedCount}/{totalCount}
                    </span>
                </div>
            </CardHeader>
            <CardContent>
                <div className="space-y-2">
                    {checklistItems.map((item) => {
                        const passed = checklist[item.key as keyof Checklist];
                        return (
                            <div
                                key={item.key}
                                className="flex items-center justify-between py-1 text-sm"
                            >
                                <div className="flex items-center gap-2">
                                    {passed ? (
                                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                                    ) : (
                                        <XCircle className="w-4 h-4 text-red-400" />
                                    )}
                                    <span className={passed ? "text-slate-100" : "text-slate-500"}>
                                        {item.label}
                                    </span>
                                </div>
                                <span className="text-xs text-slate-600">{item.rule}</span>
                            </div>
                        );
                    })}
                </div>
            </CardContent>
        </Card>
    );
}
