'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Brain, BookOpen, Target, Clock } from 'lucide-react';
import { AgentDecision } from '@/lib/api';

interface ReasoningPanelProps {
    decision: AgentDecision | null;
    isLoading?: boolean;
    className?: string;
}

export function ReasoningPanel({ decision, isLoading = false, className = '' }: ReasoningPanelProps) {
    const [isExpanded, setIsExpanded] = useState(true);

    if (isLoading) {
        return (
            <div className={`bg-slate-800 rounded-lg p-4 ${className}`}>
                <div className="flex items-center gap-2">
                    <Brain className="w-5 h-5 text-purple-400 animate-pulse" />
                    <span className="text-slate-300">Agent is reasoning...</span>
                </div>
                <div className="mt-4 space-y-2">
                    <div className="h-4 bg-slate-700 rounded animate-pulse w-3/4"></div>
                    <div className="h-4 bg-slate-700 rounded animate-pulse w-1/2"></div>
                    <div className="h-4 bg-slate-700 rounded animate-pulse w-5/6"></div>
                </div>
            </div>
        );
    }

    if (!decision) {
        return (
            <div className={`bg-slate-800 rounded-lg p-4 ${className}`}>
                <div className="flex items-center gap-2 text-slate-500">
                    <Brain className="w-5 h-5" />
                    <span>No analysis yet</span>
                </div>
            </div>
        );
    }

    const decisionColor = {
        'TRADE': 'text-green-400',
        'WAIT': 'text-yellow-400',
        'NO_TRADE': 'text-red-400'
    }[decision.decision] || 'text-slate-400';

    const confidenceColor = decision.confidence >= 0.7
        ? 'text-green-400'
        : decision.confidence >= 0.5
            ? 'text-yellow-400'
            : 'text-red-400';

    return (
        <div className={`bg-slate-800 rounded-lg overflow-hidden ${className}`}>
            {/* Header */}
            <div
                className="flex items-center justify-between p-4 cursor-pointer hover:bg-slate-700/50"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <div className="flex items-center gap-3">
                    <Brain className="w-5 h-5 text-purple-400" />
                    <span className="font-semibold text-white">Agent Reasoning</span>
                    <span className={`font-bold ${decisionColor}`}>{decision.decision}</span>
                    <span className={`text-sm ${confidenceColor}`}>
                        ({Math.round(decision.confidence * 100)}% confidence)
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">{decision.latency_ms}ms</span>
                    {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-slate-400" />
                    ) : (
                        <ChevronDown className="w-4 h-4 text-slate-400" />
                    )}
                </div>
            </div>

            {/* Content */}
            {isExpanded && (
                <div className="border-t border-slate-700 p-4 space-y-4">
                    {/* Brief Reason */}
                    <div>
                        <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
                            <Target className="w-4 h-4" />
                            Summary
                        </div>
                        <p className="text-white">{decision.brief_reason}</p>
                    </div>

                    {/* Rule Citations */}
                    {decision.rule_citations && decision.rule_citations.length > 0 && (
                        <div>
                            <div className="flex items-center gap-2 text-slate-400 text-sm mb-2">
                                <BookOpen className="w-4 h-4" />
                                Rules Applied
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {decision.rule_citations.map((rule, i) => (
                                    <span
                                        key={i}
                                        className="px-2 py-1 bg-purple-900/50 text-purple-300 rounded text-sm"
                                    >
                                        {rule}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Setup Details */}
                    {decision.setup && (
                        <div>
                            <div className="flex items-center gap-2 text-slate-400 text-sm mb-2">
                                <Target className="w-4 h-4" />
                                Trade Setup
                            </div>
                            <div className="bg-slate-900 rounded p-3 space-y-2 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-slate-400">Direction:</span>
                                    <span className={decision.setup.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}>
                                        {decision.setup.direction}
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-400">Entry Zone:</span>
                                    <span className="text-white">
                                        {decision.setup.entry_zone.low.toFixed(5)} - {decision.setup.entry_zone.high.toFixed(5)}
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-400">Stop Loss:</span>
                                    <span className="text-red-400">{decision.setup.stop_loss.toFixed(5)}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-400">Take Profits:</span>
                                    <span className="text-green-400">
                                        {decision.setup.take_profits.map(tp => tp.toFixed(5)).join(', ')}
                                    </span>
                                </div>
                                {decision.setup.invalidation && (
                                    <div className="flex justify-between">
                                        <span className="text-slate-400">Invalidation:</span>
                                        <span className="text-yellow-400">{decision.setup.invalidation}</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Full Reasoning (verbose mode) */}
                    {decision.reasoning && (
                        <div>
                            <div className="flex items-center gap-2 text-slate-400 text-sm mb-2">
                                <Brain className="w-4 h-4" />
                                Chain of Thought
                            </div>
                            <div className="bg-slate-900 rounded p-3">
                                <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono">
                                    {decision.reasoning}
                                </pre>
                            </div>
                        </div>
                    )}

                    {/* Mode indicator */}
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                        <Clock className="w-3 h-3" />
                        Mode: {decision.mode}
                    </div>
                </div>
            )}
        </div>
    );
}
