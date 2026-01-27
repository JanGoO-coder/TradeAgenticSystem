"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import { GlassBoxViewer } from "@/components/analysis/GlassBoxViewer";
import { AgentFlowDiagram } from "@/components/analysis/AgentFlowDiagram";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    ArrowLeft,
    Eye,
    Play,
    Upload,
    History,
    Search
} from "lucide-react";
import Link from "next/link";
import { getHealth } from "@/lib/api";

export default function ReplayPage() {
    const [sessionId, setSessionId] = useState<string>("");
    const [loadedSessionId, setLoadedSessionId] = useState<string | undefined>();
    const [activeTab, setActiveTab] = useState<string>("viewer");

    const { data: health } = useQuery({
        queryKey: ["health"],
        queryFn: getHealth,
        refetchInterval: 5000,
    });

    const handleLoadSession = () => {
        if (sessionId.trim()) {
            setLoadedSessionId(sessionId.trim());
        } else {
            // Load latest session if no ID provided
            setLoadedSessionId(undefined);
        }
    };

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100">
            <Header
                mode={health?.mode || "ANALYSIS_ONLY"}
                agentAvailable={health?.agent_available || false}
            />

            <main className="container mx-auto px-4 py-6 space-y-6">
                {/* Page Header */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Link href="/">
                            <Button variant="ghost" size="sm">
                                <ArrowLeft className="w-4 h-4 mr-2" />
                                Back
                            </Button>
                        </Link>
                        <div>
                            <h1 className="text-2xl font-bold flex items-center gap-2">
                                <Eye className="w-6 h-6 text-blue-400" />
                                Glass Box Replay
                            </h1>
                            <p className="text-sm text-slate-400">
                                Watch the system think — see every agent decision in real-time
                            </p>
                        </div>
                    </div>

                    <Badge variant="outline" className="text-blue-400 border-blue-400/30">
                        Simulation Replay
                    </Badge>
                </div>

                {/* Session Loader */}
                <Card className="border-slate-800 bg-slate-900/50">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-sm font-medium text-slate-300 flex items-center gap-2">
                            <History className="w-4 h-4" />
                            Load Session
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-end gap-4">
                            <div className="flex-1 space-y-2">
                                <Label htmlFor="sessionId" className="text-xs text-slate-400">
                                    Session ID (leave empty to load latest)
                                </Label>
                                <div className="flex gap-2">
                                    <Input
                                        id="sessionId"
                                        placeholder="e.g., sim_eurusd_2024_001"
                                        value={sessionId}
                                        onChange={(e) => setSessionId(e.target.value)}
                                        className="bg-slate-800 border-slate-700"
                                    />
                                    <Button onClick={handleLoadSession}>
                                        <Search className="w-4 h-4 mr-2" />
                                        Load
                                    </Button>
                                </div>
                            </div>
                            <div className="text-sm text-slate-500">
                                or
                            </div>
                            <Button variant="outline" disabled>
                                <Upload className="w-4 h-4 mr-2" />
                                Import JSON
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* Main Content */}
                <Tabs value={activeTab} onValueChange={setActiveTab}>
                    <TabsList className="bg-slate-800">
                        <TabsTrigger value="viewer" className="flex items-center gap-2">
                            <Play className="w-4 h-4" />
                            Replay Viewer
                        </TabsTrigger>
                        <TabsTrigger value="flow" className="flex items-center gap-2">
                            <Eye className="w-4 h-4" />
                            Agent Flow
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="viewer" className="mt-4">
                        <GlassBoxViewer
                            sessionId={loadedSessionId}
                            autoLoad={true}
                        />
                    </TabsContent>

                    <TabsContent value="flow" className="mt-4 space-y-4">
                        <AgentFlowDiagram compact={false} />

                        <Card className="border-slate-800 bg-slate-900/50">
                            <CardHeader>
                                <CardTitle className="text-sm">Agent Responsibilities</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm">
                                    <div className="p-3 bg-purple-500/10 border border-purple-500/30 rounded-lg">
                                        <h4 className="font-medium text-purple-400 mb-1">Trader (You)</h4>
                                        <p className="text-slate-400 text-xs">
                                            Initiates sessions, approves trades, monitors positions
                                        </p>
                                    </div>
                                    <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                                        <h4 className="font-medium text-blue-400 mb-1">Main Agent</h4>
                                        <p className="text-slate-400 text-xs">
                                            Orchestrates workflow, manages state, controls time
                                        </p>
                                    </div>
                                    <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                                        <h4 className="font-medium text-amber-400 mb-1">Strategy Agent</h4>
                                        <p className="text-slate-400 text-xs">
                                            Analyzes market context, determines bias, checks environment
                                        </p>
                                    </div>
                                    <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                                        <h4 className="font-medium text-emerald-400 mb-1">Worker Agent</h4>
                                        <p className="text-slate-400 text-xs">
                                            Fetches data, scans patterns, executes orders
                                        </p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>

                {/* Help Section */}
                <Card className="border-slate-800 bg-slate-900/30">
                    <CardContent className="pt-4">
                        <div className="flex items-start gap-4 text-sm">
                            <Eye className="w-5 h-5 text-blue-400 mt-0.5" />
                            <div className="space-y-2">
                                <p className="text-slate-300">
                                    <strong>Glass Box Replay</strong> lets you watch exactly how the trading system made each decision.
                                </p>
                                <ul className="list-disc list-inside text-slate-400 space-y-1">
                                    <li>Use playback controls to step through each tick</li>
                                    <li>Click on any message to see the full payload</li>
                                    <li>Filter by agent to focus on specific communications</li>
                                    <li>Export the replay data for offline analysis</li>
                                </ul>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </main>
        </div>
    );
}
