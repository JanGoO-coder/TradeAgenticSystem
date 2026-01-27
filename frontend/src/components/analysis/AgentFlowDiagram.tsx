"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    AgentRole,
    MessageEnvelope,
    SessionState
} from "@/lib/api";
import {
    ArrowRight,
    Brain,
    Target,
    Wrench,
    User
} from "lucide-react";

// Agent configurations
const agentConfig: Record<AgentRole, {
    icon: typeof Brain;
    color: string;
    bgColor: string;
    borderColor: string;
    description: string;
}> = {
    Trader: {
        icon: User,
        color: "text-purple-400",
        bgColor: "bg-purple-500/10",
        borderColor: "border-purple-500/30",
        description: "User Interface"
    },
    Main: {
        icon: Brain,
        color: "text-blue-400",
        bgColor: "bg-blue-500/10",
        borderColor: "border-blue-500/30",
        description: "Orchestrator"
    },
    Strategy: {
        icon: Target,
        color: "text-amber-400",
        bgColor: "bg-amber-500/10",
        borderColor: "border-amber-500/30",
        description: "Market Analyst"
    },
    Worker: {
        icon: Wrench,
        color: "text-emerald-400",
        bgColor: "bg-emerald-500/10",
        borderColor: "border-emerald-500/30",
        description: "Trade Executor"
    }
};

interface AgentFlowDiagramProps {
    messages?: MessageEnvelope[];
    sessionState?: SessionState | null;
    compact?: boolean;
}

interface AgentNodeProps {
    role: AgentRole;
    isActive: boolean;
    messageCount: number;
    compact?: boolean;
}

function AgentNode({ role, isActive, messageCount, compact = false }: AgentNodeProps) {
    const config = agentConfig[role];
    const Icon = config.icon;

    if (compact) {
        return (
            <div
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-all ${config.bgColor} ${config.borderColor} ${isActive ? "ring-2 ring-offset-2 ring-offset-slate-950 ring-blue-500" : ""
                    }`}
            >
                <Icon className={`w-4 h-4 ${config.color}`} />
                <span className={`text-sm font-medium ${config.color}`}>{role}</span>
                {messageCount > 0 && (
                    <Badge variant="secondary" className="text-xs h-5 px-1.5">
                        {messageCount}
                    </Badge>
                )}
            </div>
        );
    }

    return (
        <div
            className={`relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all ${config.bgColor} ${config.borderColor} ${isActive ? "ring-2 ring-offset-2 ring-offset-slate-950 ring-blue-500 scale-105" : ""
                }`}
        >
            <div className={`p-3 rounded-full ${config.bgColor} border ${config.borderColor}`}>
                <Icon className={`w-6 h-6 ${config.color}`} />
            </div>
            <div className="text-center">
                <p className={`font-semibold ${config.color}`}>{role}</p>
                <p className="text-xs text-slate-500">{config.description}</p>
            </div>
            {messageCount > 0 && (
                <Badge variant="secondary" className="absolute -top-2 -right-2">
                    {messageCount}
                </Badge>
            )}
        </div>
    );
}

interface FlowArrowProps {
    from: AgentRole;
    to: AgentRole;
    count: number;
    isActive: boolean;
}

function FlowArrow({ from, count, isActive }: FlowArrowProps) {
    const fromConfig = agentConfig[from];

    return (
        <div
            className={`flex items-center gap-1 transition-all ${isActive ? "opacity-100" : "opacity-40"
                }`}
        >
            <div className={`h-0.5 w-8 ${isActive ? fromConfig.color.replace("text-", "bg-") : "bg-slate-700"}`} />
            <ArrowRight className={`w-4 h-4 ${isActive ? fromConfig.color : "text-slate-700"}`} />
            {count > 0 && (
                <span className={`text-xs ${isActive ? fromConfig.color : "text-slate-600"}`}>
                    {count}
                </span>
            )}
        </div>
    );
}

export function AgentFlowDiagram({ messages = [], sessionState, compact = false }: AgentFlowDiagramProps) {
    // Calculate message stats
    const stats = useMemo(() => {
        const agentMessageCount: Record<AgentRole, number> = {
            Trader: 0,
            Main: 0,
            Strategy: 0,
            Worker: 0
        };

        const flowCount: Record<string, number> = {};

        messages.forEach((msg) => {
            agentMessageCount[msg.from_agent]++;
            const flowKey = `${msg.from_agent}->${msg.to_agent}`;
            flowCount[flowKey] = (flowCount[flowKey] || 0) + 1;
        });

        return { agentMessageCount, flowCount };
    }, [messages]);

    // Determine active agent based on session phase
    const activeAgent: AgentRole | null = useMemo(() => {
        if (!sessionState) return null;

        switch (sessionState.phase) {
            case "ANALYZING":
                return "Strategy";
            case "DECIDING":
                return "Main";
            case "EXECUTING":
            case "MONITORING":
                return "Worker";
            default:
                return "Trader";
        }
    }, [sessionState]);

    if (compact) {
        return (
            <div className="flex items-center gap-2 flex-wrap">
                {(["Trader", "Main", "Strategy", "Worker"] as AgentRole[]).map((role, idx) => (
                    <div key={role} className="flex items-center gap-2">
                        <AgentNode
                            role={role}
                            isActive={activeAgent === role}
                            messageCount={stats.agentMessageCount[role]}
                            compact
                        />
                        {idx < 3 && (
                            <ArrowRight className="w-4 h-4 text-slate-600" />
                        )}
                    </div>
                ))}
            </div>
        );
    }

    return (
        <Card className="border-slate-800 bg-slate-900/50">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-slate-300">
                    Agent Communication Flow
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="flex items-center justify-between gap-4">
                    {/* Trader Node */}
                    <AgentNode
                        role="Trader"
                        isActive={activeAgent === "Trader"}
                        messageCount={stats.agentMessageCount.Trader}
                    />

                    {/* Trader -> Main Flow */}
                    <FlowArrow
                        from="Trader"
                        to="Main"
                        count={stats.flowCount["Trader->Main"] || 0}
                        isActive={activeAgent === "Trader" || activeAgent === "Main"}
                    />

                    {/* Main Node */}
                    <AgentNode
                        role="Main"
                        isActive={activeAgent === "Main"}
                        messageCount={stats.agentMessageCount.Main}
                    />

                    {/* Main -> Strategy Flow */}
                    <div className="flex flex-col items-center gap-2">
                        <FlowArrow
                            from="Main"
                            to="Strategy"
                            count={stats.flowCount["Main->Strategy"] || 0}
                            isActive={activeAgent === "Main" || activeAgent === "Strategy"}
                        />
                        <FlowArrow
                            from="Strategy"
                            to="Main"
                            count={stats.flowCount["Strategy->Main"] || 0}
                            isActive={activeAgent === "Strategy" || activeAgent === "Main"}
                        />
                    </div>

                    {/* Strategy Node */}
                    <AgentNode
                        role="Strategy"
                        isActive={activeAgent === "Strategy"}
                        messageCount={stats.agentMessageCount.Strategy}
                    />

                    {/* Strategy -> Worker Flow (via Main) */}
                    <div className="flex flex-col items-center gap-2">
                        <FlowArrow
                            from="Main"
                            to="Worker"
                            count={stats.flowCount["Main->Worker"] || 0}
                            isActive={activeAgent === "Main" || activeAgent === "Worker"}
                        />
                        <FlowArrow
                            from="Worker"
                            to="Main"
                            count={stats.flowCount["Worker->Main"] || 0}
                            isActive={activeAgent === "Worker" || activeAgent === "Main"}
                        />
                    </div>

                    {/* Worker Node */}
                    <AgentNode
                        role="Worker"
                        isActive={activeAgent === "Worker"}
                        messageCount={stats.agentMessageCount.Worker}
                    />
                </div>

                {/* Phase indicator */}
                {sessionState && (
                    <div className="mt-4 pt-4 border-t border-slate-800 flex items-center justify-center gap-4">
                        <span className="text-sm text-slate-500">Current Phase:</span>
                        <Badge
                            variant="outline"
                            className={`${agentConfig[activeAgent || "Trader"].color} ${agentConfig[activeAgent || "Trader"].borderColor}`}
                        >
                            {sessionState.phase}
                        </Badge>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

export default AgentFlowDiagram;
