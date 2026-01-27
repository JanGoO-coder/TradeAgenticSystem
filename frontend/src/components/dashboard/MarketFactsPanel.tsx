"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getMarketFacts } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp, Eye, RefreshCw } from "lucide-react";

interface MarketFactsPanelProps {
    className?: string;
}

export function MarketFactsPanel({ className }: MarketFactsPanelProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(["structure"]));

    const { data, isLoading, refetch } = useQuery({
        queryKey: ["marketFacts"],
        queryFn: getMarketFacts,
        staleTime: 10000,
        enabled: isExpanded, // Only fetch when expanded
    });

    const toggleSection = (section: string) => {
        const newSet = new Set(expandedSections);
        if (newSet.has(section)) {
            newSet.delete(section);
        } else {
            newSet.add(section);
        }
        setExpandedSections(newSet);
    };

    const renderValue = (value: any, depth: number = 0): JSX.Element => {
        if (value === null || value === undefined) {
            return <span className="text-slate-500">—</span>;
        }

        if (typeof value === "boolean") {
            return (
                <span className={value ? "text-emerald-400" : "text-red-400"}>
                    {value ? "Yes" : "No"}
                </span>
            );
        }

        if (typeof value === "number") {
            return <span className="text-amber-400 font-mono">{value.toFixed(5)}</span>;
        }

        if (typeof value === "string") {
            return <span className="text-slate-300">{value}</span>;
        }

        if (Array.isArray(value)) {
            if (value.length === 0) {
                return <span className="text-slate-500">Empty</span>;
            }
            return (
                <div className="space-y-1 mt-1">
                    {value.slice(0, 5).map((item, i) => (
                        <div key={i} className="text-xs bg-slate-800/50 px-2 py-1 rounded">
                            {typeof item === "object" ? JSON.stringify(item) : String(item)}
                        </div>
                    ))}
                    {value.length > 5 && (
                        <div className="text-xs text-slate-500">
                            +{value.length - 5} more...
                        </div>
                    )}
                </div>
            );
        }

        if (typeof value === "object") {
            return (
                <div className="space-y-1 mt-1 pl-2 border-l border-slate-700">
                    {Object.entries(value).slice(0, 10).map(([k, v]) => (
                        <div key={k} className="text-xs">
                            <span className="text-slate-400">{k}:</span>{" "}
                            {renderValue(v, depth + 1)}
                        </div>
                    ))}
                </div>
            );
        }

        return <span className="text-slate-300">{String(value)}</span>;
    };

    const facts = data?.facts;

    return (
        <Card className={`bg-slate-900 border-slate-800 ${className}`}>
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
                        <Eye className="w-4 h-4 text-purple-400" />
                        Market Facts (Debug)
                    </CardTitle>
                    <div className="flex items-center gap-2">
                        {isExpanded && (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => refetch()}
                                className="h-6 px-2"
                            >
                                <RefreshCw className={`w-3 h-3 ${isLoading ? "animate-spin" : ""}`} />
                            </Button>
                        )}
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setIsExpanded(!isExpanded)}
                            className="h-6 px-2"
                        >
                            {isExpanded ? (
                                <ChevronUp className="w-4 h-4" />
                            ) : (
                                <ChevronDown className="w-4 h-4" />
                            )}
                        </Button>
                    </div>
                </div>
            </CardHeader>

            {isExpanded && (
                <CardContent className="pt-0">
                    {!facts && !isLoading && (
                        <div className="text-sm text-slate-500 text-center py-4">
                            {data?.message || "No market facts available. Run an analysis first."}
                        </div>
                    )}

                    {isLoading && (
                        <div className="text-sm text-slate-500 text-center py-4">
                            Loading market facts...
                        </div>
                    )}

                    {facts && (
                        <div className="space-y-2">
                            {/* Structure Section */}
                            <SectionHeader
                                title="📊 Structure"
                                section="structure"
                                isExpanded={expandedSections.has("structure")}
                                onToggle={toggleSection}
                            />
                            {expandedSections.has("structure") && facts.structure && (
                                <div className="text-xs space-y-1 pl-2">
                                    {Object.entries(facts.structure).map(([tf, data]) => (
                                        <div key={tf} className="bg-slate-800/30 p-2 rounded">
                                            <span className="text-emerald-400 font-medium">{tf}:</span>
                                            {renderValue(data)}
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* FVGs Section */}
                            <SectionHeader
                                title="🟨 Fair Value Gaps"
                                section="fvgs"
                                isExpanded={expandedSections.has("fvgs")}
                                onToggle={toggleSection}
                            />
                            {expandedSections.has("fvgs") && facts.fvgs && (
                                <div className="text-xs pl-2">
                                    {Object.entries(facts.fvgs).map(([tf, data]) => (
                                        <div key={tf} className="mb-2">
                                            <span className="text-amber-400">{tf}:</span>
                                            {renderValue(data)}
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* Session Section */}
                            <SectionHeader
                                title="⏰ Session"
                                section="session"
                                isExpanded={expandedSections.has("session")}
                                onToggle={toggleSection}
                            />
                            {expandedSections.has("session") && facts.session && (
                                <div className="text-xs pl-2">{renderValue(facts.session)}</div>
                            )}

                            {/* Levels Section */}
                            <SectionHeader
                                title="📍 Liquidity Levels"
                                section="levels"
                                isExpanded={expandedSections.has("levels")}
                                onToggle={toggleSection}
                            />
                            {expandedSections.has("levels") && facts.levels && (
                                <div className="text-xs pl-2">{renderValue(facts.levels)}</div>
                            )}

                            {/* Sweeps Section */}
                            <SectionHeader
                                title="🔄 Sweep Events"
                                section="sweeps"
                                isExpanded={expandedSections.has("sweeps")}
                                onToggle={toggleSection}
                            />
                            {expandedSections.has("sweeps") && facts.sweeps && (
                                <div className="text-xs pl-2">{renderValue(facts.sweeps)}</div>
                            )}
                        </div>
                    )}
                </CardContent>
            )}
        </Card>
    );
}

function SectionHeader({
    title,
    section,
    isExpanded,
    onToggle,
}: {
    title: string;
    section: string;
    isExpanded: boolean;
    onToggle: (s: string) => void;
}) {
    return (
        <button
            onClick={() => onToggle(section)}
            className="w-full flex items-center justify-between text-xs text-slate-300 hover:text-slate-100 py-1 px-2 bg-slate-800/50 rounded"
        >
            <span>{title}</span>
            {isExpanded ? (
                <ChevronUp className="w-3 h-3" />
            ) : (
                <ChevronDown className="w-3 h-3" />
            )}
        </button>
    );
}
