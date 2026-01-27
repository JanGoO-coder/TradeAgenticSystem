"use client";

import { useState } from "react";
import { Header } from "@/components/layout/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getHealth, listStrategyFiles, getStrategyFile, addStrategy, deleteStrategyFile, reindexStrategies, listAllRules, getIndexStatus, StrategyFile } from "@/lib/api";
import { BookOpen, CheckCircle2, ChevronDown, ChevronRight, Target, TrendingUp, Clock, Shield, AlertTriangle, Zap, FileText, Plus, Trash2, RefreshCw, Database, Upload } from "lucide-react";

const rulesData = {
    bias: [
        { id: "1.1", name: "HTF Bias", description: "1H directional bias via HH/HL (bullish) or LH/LL (bearish).", details: "The 1H chart determines overall direction.", importance: "critical" },
        { id: "1.2", name: "LTF Alignment", description: "15M must align with 1H bias direction.", details: "LTF provides entry precision.", importance: "high" },
    ],
    structure: [
        { id: "2.1", name: "Swing Points", description: "Identify swing highs/lows using fractal logic.", details: "Min 2-3 candles lookback.", importance: "critical" },
        { id: "2.3", name: "MSS", description: "Displacement through prior swing signals a shift.", details: "Bullish MSS breaks above swing high with momentum.", importance: "high" },
    ],
    liquidity: [
        { id: "3.4", name: "Liquidity Sweep", description: "Price must sweep liquidity before entry.", details: "Trap sellers before longs, trap buyers before shorts.", importance: "critical" },
        { id: "3.5", name: "Equal Highs/Lows", description: "Equal highs/lows represent liquidity pools.", details: "Stop orders concentrate at these levels.", importance: "medium" },
    ],
    pdArrays: [
        { id: "5.1", name: "Premium/Discount", description: "Longs in discount (<50%), shorts in premium (>50%).", details: "Calculate from swing low to high.", importance: "high" },
        { id: "5.2", name: "FVG", description: "3-candle imbalance creates FVG.", details: "Gap between C1 high and C3 low (bullish).", importance: "critical" },
    ],
    entry: [
        { id: "6.1", name: "OTE Zone", description: "Entry at 62%-79% retracement.", details: "High-probability Fibonacci zone.", importance: "high" },
        { id: "6.5", name: "ICT 2022 Model", description: "Sweep + displacement + FVG.", details: "Complete entry model sequence.", importance: "critical" },
    ],
    risk: [
        { id: "7.1", name: "Fixed Risk", description: "Risk 1% per trade.", details: "Consistent position sizing.", importance: "critical" },
        { id: "7.2", name: "R:R Minimum", description: "Minimum 1:2 risk-reward.", details: "Ensures profitability at <50% win rate.", importance: "critical" },
    ],
    session: [
        { id: "8.1", name: "Kill Zones", description: "Trade London (2-5 EST) or NY (7-10 EST).", details: "Highest probability windows.", importance: "critical" },
        { id: "8.4", name: "News Rules", description: "No entries 30min around news.", details: "Avoid FOMC, NFP, CPI volatility.", importance: "high" },
    ]
};

const categoryConfig = {
    bias: { label: "Bias", icon: TrendingUp, color: "text-emerald-400" },
    structure: { label: "Structure", icon: Target, color: "text-blue-400" },
    liquidity: { label: "Liquidity", icon: Zap, color: "text-yellow-400" },
    pdArrays: { label: "PD Arrays", icon: Target, color: "text-purple-400" },
    entry: { label: "Entry", icon: Shield, color: "text-orange-400" },
    risk: { label: "Risk", icon: AlertTriangle, color: "text-red-400" },
    session: { label: "Session", icon: Clock, color: "text-cyan-400" }
};

function RuleCard({ rule }: { rule: typeof rulesData.bias[0] }) {
    const [isExpanded, setIsExpanded] = useState(false);
    const colors = { critical: "bg-red-500/20 text-red-400", high: "bg-yellow-500/20 text-yellow-400", medium: "bg-blue-500/20 text-blue-400" };
    return (
        <div className="bg-slate-800/50 rounded-lg overflow-hidden">
            <button onClick={() => setIsExpanded(!isExpanded)} className="w-full flex items-center gap-2 p-3 hover:bg-slate-800 text-left">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                        <Badge variant="outline" className="text-[10px] font-mono">{rule.id}</Badge>
                        <span className="text-sm font-medium text-slate-100">{rule.name}</span>
                        <Badge className={`text-[10px] ${colors[rule.importance as keyof typeof colors]}`}>{rule.importance}</Badge>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">{rule.description}</p>
                </div>
                {isExpanded ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />}
            </button>
            {isExpanded && (
                <div className="px-3 pb-3 pt-0 pl-9">
                    <Separator className="bg-slate-700 mb-2" />
                    <p className="text-xs text-slate-400">{rule.details}</p>
                </div>
            )}
        </div>
    );
}

export default function RulesPage() {
    const { data: health } = useQuery({ queryKey: ["health"], queryFn: getHealth });
    return (
        <div className="flex flex-col h-full w-full">
            <Header mode={health?.mode || "ANALYSIS_ONLY"} agentAvailable={health?.agent_available || false} />
            <ScrollArea className="flex-1 min-h-0">
                <div className="p-4 min-w-0">
                    <div className="flex items-center gap-3 mb-4">
                        <BookOpen className="w-5 h-5 text-slate-400" />
                        <h2 className="text-lg font-semibold text-slate-100">ICT Trading Rules</h2>
                    </div>
                    <Tabs defaultValue="bias" className="w-full">
                        <TabsList className="bg-slate-800 mb-4 flex flex-wrap h-auto gap-1 p-1">
                            {Object.entries(categoryConfig).map(([key, cfg]) => (
                                <TabsTrigger key={key} value={key} className="text-xs data-[state=active]:bg-slate-700">
                                    <cfg.icon className={`w-3 h-3 mr-1 ${cfg.color}`} />{cfg.label}
                                </TabsTrigger>
                            ))}
                        </TabsList>
                        {Object.entries(rulesData).map(([cat, rules]) => {
                            const cfg = categoryConfig[cat as keyof typeof categoryConfig];
                            return (
                                <TabsContent key={cat} value={cat}>
                                    <Card className="bg-slate-900 border-slate-800">
                                        <CardHeader className="pb-2"><CardTitle className="flex items-center gap-2 text-base"><cfg.icon className={`w-4 h-4 ${cfg.color}`} />{cfg.label}</CardTitle></CardHeader>
                                        <CardContent>
                                            <div className="space-y-2">{rules.map((r) => <RuleCard key={r.id} rule={r} />)}</div>
                                        </CardContent>
                                    </Card>
                                </TabsContent>
                            );
                        })}
                    </Tabs>

                    {/* Strategy Files Management Section */}
                    <StrategyFilesManager />
                </div>
            </ScrollArea>
        </div>
    );
}

function StrategyFilesManager() {
    const queryClient = useQueryClient();
    const [showAddForm, setShowAddForm] = useState(false);
    const [newStrategyName, setNewStrategyName] = useState("");
    const [newStrategyContent, setNewStrategyContent] = useState("");
    const [selectedFile, setSelectedFile] = useState<string | null>(null);
    const [fileContent, setFileContent] = useState("");

    // Queries
    const { data: files, isLoading: filesLoading } = useQuery({
        queryKey: ["strategyFiles"],
        queryFn: listStrategyFiles,
    });

    const { data: indexStatus } = useQuery({
        queryKey: ["indexStatus"],
        queryFn: getIndexStatus,
    });

    const { data: allRules } = useQuery({
        queryKey: ["allRules"],
        queryFn: listAllRules,
    });

    const { data: selectedFileData } = useQuery({
        queryKey: ["strategyFile", selectedFile],
        queryFn: () => selectedFile ? getStrategyFile(selectedFile) : null,
        enabled: !!selectedFile,
    });

    // Mutations
    const reindexMutation = useMutation({
        mutationFn: reindexStrategies,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["indexStatus"] });
            queryClient.invalidateQueries({ queryKey: ["allRules"] });
        },
    });

    const addMutation = useMutation({
        mutationFn: () => addStrategy(newStrategyName, newStrategyContent),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["strategyFiles"] });
            setShowAddForm(false);
            setNewStrategyName("");
            setNewStrategyContent("");
        },
    });

    const deleteMutation = useMutation({
        mutationFn: (filename: string) => deleteStrategyFile(filename),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["strategyFiles"] });
            setSelectedFile(null);
        },
    });

    return (
        <div className="mt-6 space-y-4">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Database className="w-5 h-5 text-purple-400" />
                    <h2 className="text-lg font-semibold text-slate-100">Strategy Files</h2>
                    <Badge variant="outline" className="text-xs">
                        {indexStatus?.chunks_indexed || 0} chunks indexed
                    </Badge>
                </div>
                <div className="flex gap-2">
                    <Button
                        size="sm"
                        variant="outline"
                        onClick={() => reindexMutation.mutate()}
                        disabled={reindexMutation.isPending}
                    >
                        <RefreshCw className={`w-4 h-4 mr-1 ${reindexMutation.isPending ? 'animate-spin' : ''}`} />
                        Reindex
                    </Button>
                    <Button
                        size="sm"
                        onClick={() => setShowAddForm(true)}
                    >
                        <Plus className="w-4 h-4 mr-1" />
                        Add Strategy
                    </Button>
                </div>
            </div>

            {/* Index Status */}
            <div className="grid grid-cols-3 gap-4">
                <Card className="bg-slate-900 border-slate-800">
                    <CardContent className="p-3">
                        <div className="text-xs text-slate-400">Strategy Files</div>
                        <div className="text-xl font-bold text-slate-100">{files?.total || 0}</div>
                    </CardContent>
                </Card>
                <Card className="bg-slate-900 border-slate-800">
                    <CardContent className="p-3">
                        <div className="text-xs text-slate-400">Rules Indexed</div>
                        <div className="text-xl font-bold text-purple-400">{allRules?.count || 0}</div>
                    </CardContent>
                </Card>
                <Card className="bg-slate-900 border-slate-800">
                    <CardContent className="p-3">
                        <div className="text-xs text-slate-400">Vector Store</div>
                        <div className={`text-xl font-bold ${indexStatus?.vector_store?.healthy ? 'text-emerald-400' : 'text-yellow-400'}`}>
                            {indexStatus?.vector_store?.healthy ? 'Connected' : 'Offline'}
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Add Strategy Form */}
            {showAddForm && (
                <Card className="bg-slate-900 border-slate-800">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Add New Strategy</CardTitle>
                        <CardDescription className="text-xs">Create a new markdown strategy file</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <Input
                            placeholder="Strategy name (e.g., My_Custom_Strategy)"
                            value={newStrategyName}
                            onChange={(e) => setNewStrategyName(e.target.value)}
                            className="bg-slate-800 border-slate-700"
                        />
                        <Textarea
                            placeholder="# Strategy Content (Markdown)&#10;&#10;## Rule 1.0 - Example&#10;Description here..."
                            value={newStrategyContent}
                            onChange={(e) => setNewStrategyContent(e.target.value)}
                            className="bg-slate-800 border-slate-700 min-h-[200px] font-mono text-xs"
                        />
                        <div className="flex gap-2">
                            <Button size="sm" onClick={() => addMutation.mutate()} disabled={addMutation.isPending || !newStrategyName || !newStrategyContent}>
                                {addMutation.isPending ? 'Adding...' : 'Add Strategy'}
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => setShowAddForm(false)}>Cancel</Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* File List */}
            <Card className="bg-slate-900 border-slate-800">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                        <FileText className="w-4 h-4" />
                        Available Strategy Files
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {filesLoading ? (
                        <div className="text-slate-400 text-sm">Loading...</div>
                    ) : files?.files.length === 0 ? (
                        <div className="text-slate-400 text-sm">No strategy files found. Add one to get started.</div>
                    ) : (
                        <div className="space-y-2">
                            {files?.files.map((file: StrategyFile) => (
                                <div
                                    key={file.path}
                                    className={`flex items-center justify-between p-2 rounded-lg cursor-pointer transition-colors ${
                                        selectedFile === file.path ? 'bg-slate-700' : 'bg-slate-800/50 hover:bg-slate-800'
                                    }`}
                                    onClick={() => setSelectedFile(file.path)}
                                >
                                    <div className="flex items-center gap-2">
                                        <FileText className="w-4 h-4 text-slate-400" />
                                        <div>
                                            <div className="text-sm font-medium text-slate-100">{file.filename}</div>
                                            <div className="text-xs text-slate-400">
                                                {file.rule_count} rules • {(file.size_bytes / 1024).toFixed(1)} KB
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Badge variant="outline" className="text-xs">{file.path}</Badge>
                                        <Button
                                            size="icon"
                                            variant="ghost"
                                            className="h-7 w-7 text-red-400 hover:text-red-300 hover:bg-red-900/20"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                if (confirm(`Delete ${file.filename}?`)) {
                                                    deleteMutation.mutate(file.path);
                                                }
                                            }}
                                        >
                                            <Trash2 className="w-3 h-3" />
                                        </Button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* File Preview */}
            {selectedFile && selectedFileData && (
                <Card className="bg-slate-900 border-slate-800">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Preview: {selectedFileData.filename}</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <ScrollArea className="h-[300px]">
                            <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono">
                                {selectedFileData.content}
                            </pre>
                        </ScrollArea>
                    </CardContent>
                </Card>
            )}

            {/* Rules List */}
            {allRules && allRules.count > 0 && (
                <Card className="bg-slate-900 border-slate-800">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Indexed Rules ({allRules.count})</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex flex-wrap gap-1">
                            {allRules.rules.map((ruleId: string) => (
                                <Badge key={ruleId} variant="secondary" className="text-xs font-mono">
                                    {ruleId}
                                </Badge>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
