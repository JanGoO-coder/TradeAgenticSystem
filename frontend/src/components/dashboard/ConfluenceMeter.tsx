"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Gauge } from "lucide-react";

interface ConfluenceMeterProps {
    score: number;
    confidence: number;
}

export function ConfluenceMeter({ score, confidence }: ConfluenceMeterProps) {
    const getScoreColor = (score: number) => {
        if (score >= 8) return "text-emerald-400";
        if (score >= 5) return "text-yellow-400";
        return "text-red-400";
    };

    const getConfidenceColor = (confidence: number) => {
        if (confidence >= 0.7) return "bg-emerald-500";
        if (confidence >= 0.5) return "bg-yellow-500";
        return "bg-red-500";
    };

    return (
        <Card className="bg-slate-900 border-slate-800">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
                    <Gauge className="w-4 h-4" />
                    Confluence Score
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-4">
                    {/* Score Display */}
                    <div className="text-center">
                        <div className={`text-5xl font-bold ${getScoreColor(score)}`}>
                            {score}
                            <span className="text-xl text-slate-500">/10</span>
                        </div>
                    </div>

                    {/* Confidence Bar */}
                    <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                            <span className="text-slate-400">Confidence</span>
                            <span className="text-slate-100">{(confidence * 100).toFixed(0)}%</span>
                        </div>
                        <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                            <div
                                className={`h-full rounded-full transition-all ${getConfidenceColor(confidence)}`}
                                style={{ width: `${confidence * 100}%` }}
                            />
                        </div>
                    </div>

                    {/* Score Breakdown Legend */}
                    <div className="text-xs text-slate-500 space-y-1">
                        <div className="flex justify-between">
                            <span>8-10:</span>
                            <span className="text-emerald-400">High Probability</span>
                        </div>
                        <div className="flex justify-between">
                            <span>5-7:</span>
                            <span className="text-yellow-400">Moderate</span>
                        </div>
                        <div className="flex justify-between">
                            <span>1-4:</span>
                            <span className="text-red-400">Low Probability</span>
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
