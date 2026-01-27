"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getStrategies, switchStrategy, StrategyListResponse } from "@/lib/api";
import { ChevronDown, BookOpen, Check, Loader2 } from "lucide-react";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
    DropdownMenuSeparator,
    DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

interface StrategySelectorProps {
    className?: string;
}

export function StrategySelector({ className }: StrategySelectorProps) {
    const [selectedStrategy, setSelectedStrategy] = useState<string>("active_strategy");
    const queryClient = useQueryClient();

    const { data: strategies, isLoading } = useQuery({
        queryKey: ["strategies"],
        queryFn: getStrategies,
        staleTime: 30000,
    });

    const switchMutation = useMutation({
        mutationFn: switchStrategy,
        onSuccess: (data) => {
            if (data.success && data.new_strategy) {
                setSelectedStrategy(data.new_strategy);
                queryClient.invalidateQueries({ queryKey: ["strategies"] });
            }
        },
    });

    const formatStrategyName = (name: string): string => {
        // Convert file name to display name
        // e.g., "ict_2022_model" -> "ICT 2022 Model"
        return name
            .replace(/_/g, " ")
            .replace(/\b\w/g, (c) => c.toUpperCase())
            .replace("Ict", "ICT")
            .replace("Ote", "OTE");
    };

    const getStrategyIcon = (name: string): string => {
        if (name.includes("ict_2022")) return "🎯";
        if (name.includes("ote")) return "📊";
        if (name.includes("silver")) return "🥈";
        return "📋";
    };

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button
                    variant="outline"
                    className={`bg-slate-800 border-slate-700 hover:bg-slate-700 text-slate-200 ${className}`}
                    disabled={isLoading || switchMutation.isPending}
                >
                    {switchMutation.isPending ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                        <BookOpen className="w-4 h-4 mr-2 text-amber-400" />
                    )}
                    <span className="truncate max-w-[120px]">
                        {formatStrategyName(selectedStrategy)}
                    </span>
                    <ChevronDown className="w-4 h-4 ml-2 opacity-50" />
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
                align="start"
                className="w-56 bg-slate-900 border-slate-700"
            >
                <DropdownMenuLabel className="text-slate-400 text-xs">
                    Trading Strategies
                </DropdownMenuLabel>
                <DropdownMenuSeparator className="bg-slate-700" />

                {strategies?.available_strategies.map((strategy) => (
                    <DropdownMenuItem
                        key={strategy}
                        onClick={() => switchMutation.mutate(strategy)}
                        className="flex items-center justify-between cursor-pointer hover:bg-slate-800"
                    >
                        <span className="flex items-center gap-2">
                            <span>{getStrategyIcon(strategy)}</span>
                            <span className="text-slate-200">
                                {formatStrategyName(strategy)}
                            </span>
                        </span>
                        {selectedStrategy === strategy && (
                            <Check className="w-4 h-4 text-emerald-400" />
                        )}
                    </DropdownMenuItem>
                ))}

                {!strategies?.available_strategies.length && !isLoading && (
                    <DropdownMenuItem disabled className="text-slate-500">
                        No strategies found
                    </DropdownMenuItem>
                )}

                {isLoading && (
                    <DropdownMenuItem disabled className="text-slate-500">
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Loading...
                    </DropdownMenuItem>
                )}
            </DropdownMenuContent>
        </DropdownMenu>
    );
}
