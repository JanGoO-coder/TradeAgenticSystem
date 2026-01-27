"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Separator } from "@/components/ui/separator";
import {
    Play,
    Pause,
    SkipBack,
    SkipForward,
    FastForward,
    Eye,
    Activity,
    MessageSquare,
    Clock,
    ChevronRight,
    ChevronDown,
    Download,
    Filter
} from "lucide-react";
import {
    MessageEnvelope,
    TickEvent,
    GlassBoxReplayData,
    AgentRole,
    getGlassBoxReplay,
    exportGlassBox
} from "@/lib/api";

// Agent role colors
const agentColors: Record<AgentRole, string> = {
    Trader: "text-purple-400 bg-purple-400/10 border-purple-400/30",
    Main: "text-blue-400 bg-blue-400/10 border-blue-400/30",
    Strategy: "text-amber-400 bg-amber-400/10 border-amber-400/30",
    Worker: "text-emerald-400 bg-emerald-400/10 border-emerald-400/30"
};

const agentBgColors: Record<AgentRole, string> = {
    Trader: "bg-purple-500",
    Main: "bg-blue-500",
    Strategy: "bg-amber-500",
    Worker: "bg-emerald-500"
};

// Action type badges
const actionTypeStyles: Record<string, string> = {
    GET_SNAPSHOT: "text-cyan-400 border-cyan-400/30",
    SCAN_SETUPS: "text-green-400 border-green-400/30",
    EXECUTE_ORDER: "text-red-400 border-red-400/30",
    ADVANCE_TIME: "text-slate-400 border-slate-400/30",
    GET_POSITIONS: "text-indigo-400 border-indigo-400/30",
    CLOSE_POSITION: "text-orange-400 border-orange-400/30",
    ANALYZE_CONTEXT: "text-amber-400 border-amber-400/30",
    SNAPSHOT_RESULT: "text-cyan-300 border-cyan-300/30",
    CONTEXT_RESULT: "text-amber-300 border-amber-300/30",
    SETUP_RESULT: "text-green-300 border-green-300/30",
    EXECUTION_RECEIPT: "text-red-300 border-red-300/30",
    POSITIONS_RESULT: "text-indigo-300 border-indigo-300/30",
    TIME_ADVANCED: "text-slate-300 border-slate-300/30",
    ERROR: "text-red-500 border-red-500/30"
};

interface GlassBoxViewerProps {
    sessionId?: string;
    autoLoad?: boolean;
}

interface MessageItemProps {
    message: MessageEnvelope;
    isExpanded: boolean;
    onToggle: () => void;
    isHighlighted: boolean;
}

function MessageItem({ message, isExpanded, onToggle, isHighlighted }: MessageItemProps) {
    const fromColor = agentColors[message.from_agent] || "text-slate-400";
    const toColor = agentColors[message.to_agent] || "text-slate-400";
    const actionStyle = actionTypeStyles[message.action] || "text-slate-400 border-slate-400/30";

    return (
        <div
            className={`rounded-lg border transition-all ${isHighlighted
                    ? "border-yellow-500/50 bg-yellow-500/5"
                    : "border-slate-800 bg-slate-900/50 hover:bg-slate-800/50"
                }`}
        >
            <button
                onClick={onToggle}
                className="w-full flex items-start gap-3 p-3 text-left"
            >
                <div className="flex-shrink-0 pt-0.5">
                    <MessageSquare className="w-4 h-4 text-slate-500" />
                </div>

                <div className="flex-1 min-w-0 space-y-1.5">
                    {/* Agent flow */}
                    <div className="flex items-center gap-2 flex-wrap">
                        <Badge variant="outline" className={`text-xs ${fromColor}`}>
                            {message.from_agent}
                        </Badge>
                        <ChevronRight className="w-3 h-3 text-slate-600" />
                        <Badge variant="outline" className={`text-xs ${toColor}`}>
                            {message.to_agent}
                        </Badge>
                        <Badge variant="outline" className={`text-xs ${actionStyle}`}>
                            {message.action}
                        </Badge>
                    </div>

                    {/* Timestamp and correlation */}
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                        <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(message.timestamp).toLocaleTimeString()}
                        </span>
                        <span className="font-mono truncate">
                            {message.correlation_id.slice(0, 8)}...
                        </span>
                    </div>
                </div>

                {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-slate-500 flex-shrink-0" />
                ) : (
                    <ChevronRight className="w-4 h-4 text-slate-500 flex-shrink-0" />
                )}
            </button>

            {isExpanded && (
                <div className="px-3 pb-3 space-y-2">
                    <Separator className="bg-slate-800" />

                    {/* Message ID */}
                    <div className="text-xs">
                        <span className="text-slate-500">ID: </span>
                        <span className="font-mono text-slate-400">{message.id}</span>
                    </div>

                    {/* Reply-to if present */}
                    {message.reply_to && (
                        <div className="text-xs">
                            <span className="text-slate-500">Reply to: </span>
                            <span className="font-mono text-slate-400">{message.reply_to.slice(0, 8)}...</span>
                        </div>
                    )}

                    {/* Error if present */}
                    {message.error && (
                        <div className="p-2 bg-red-500/10 border border-red-500/30 rounded text-xs text-red-400">
                            {message.error}
                        </div>
                    )}

                    {/* Payload */}
                    <div className="space-y-1">
                        <span className="text-xs text-slate-500">Payload:</span>
                        <pre className="p-2 bg-slate-950 rounded text-xs font-mono text-slate-300 overflow-x-auto max-h-40">
                            {JSON.stringify(message.payload, null, 2)}
                        </pre>
                    </div>
                </div>
            )}
        </div>
    );
}

interface TickItemProps {
    tick: TickEvent;
    isActive: boolean;
    onSelect: () => void;
}

function TickItem({ tick, isActive, onSelect }: TickItemProps) {
    return (
        <button
            onClick={onSelect}
            className={`w-full p-2 rounded-lg text-left transition-all ${isActive
                    ? "bg-blue-500/20 border border-blue-500/30"
                    : "bg-slate-900/50 hover:bg-slate-800/50 border border-transparent"
                }`}
        >
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-slate-400">#{tick.tick}</span>
                    <span className="text-xs text-slate-500">
                        {new Date(tick.time).toLocaleTimeString()}
                    </span>
                </div>
                <Badge variant="outline" className="text-xs text-slate-500">
                    {tick.events.length} events
                </Badge>
            </div>

            {/* Event summary */}
            <div className="mt-1 flex flex-wrap gap-1">
                {tick.events.slice(0, 3).map((event, idx) => (
                    <span
                        key={idx}
                        className={`inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded ${agentColors[event.agent] || "text-slate-400 bg-slate-800"
                            }`}
                    >
                        <span className={`w-1.5 h-1.5 rounded-full ${agentBgColors[event.agent] || "bg-slate-500"}`} />
                        {event.action}
                    </span>
                ))}
                {tick.events.length > 3 && (
                    <span className="text-xs text-slate-500">+{tick.events.length - 3} more</span>
                )}
            </div>
        </button>
    );
}

export function GlassBoxViewer({ sessionId, autoLoad = true }: GlassBoxViewerProps) {
    const [data, setData] = useState<GlassBoxReplayData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Playback state
    const [isPlaying, setIsPlaying] = useState(false);
    const [playbackSpeed, setPlaybackSpeed] = useState(1);
    const [currentTickIndex, setCurrentTickIndex] = useState(0);
    const playbackInterval = useRef<NodeJS.Timeout | null>(null);

    // UI state
    const [expandedMessages, setExpandedMessages] = useState<Set<string>>(new Set());
    const [agentFilter, setAgentFilter] = useState<AgentRole | "all">("all");
    const [showTimeline, setShowTimeline] = useState(true);

    // Load data
    const loadData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await getGlassBoxReplay(sessionId);
            setData(result);
            setCurrentTickIndex(0);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load Glass Box data");
        } finally {
            setLoading(false);
        }
    }, [sessionId]);

    useEffect(() => {
        if (autoLoad) {
            loadData();
        }
    }, [autoLoad, loadData]);

    // Playback control
    useEffect(() => {
        if (isPlaying && data) {
            playbackInterval.current = setInterval(() => {
                setCurrentTickIndex((prev) => {
                    if (prev >= data.ticks.length - 1) {
                        setIsPlaying(false);
                        return prev;
                    }
                    return prev + 1;
                });
            }, 1000 / playbackSpeed);
        }

        return () => {
            if (playbackInterval.current) {
                clearInterval(playbackInterval.current);
            }
        };
    }, [isPlaying, playbackSpeed, data]);

    const togglePlay = () => setIsPlaying(!isPlaying);
    const goToStart = () => {
        setCurrentTickIndex(0);
        setIsPlaying(false);
    };
    const goToEnd = () => {
        if (data) {
            setCurrentTickIndex(data.ticks.length - 1);
            setIsPlaying(false);
        }
    };
    const stepForward = () => {
        if (data && currentTickIndex < data.ticks.length - 1) {
            setCurrentTickIndex(currentTickIndex + 1);
        }
    };
    const stepBack = () => {
        if (currentTickIndex > 0) {
            setCurrentTickIndex(currentTickIndex - 1);
        }
    };

    const toggleMessageExpanded = (id: string) => {
        setExpandedMessages((prev) => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else {
                next.add(id);
            }
            return next;
        });
    };

    // Get messages for current tick
    const currentTick = data?.ticks[currentTickIndex];
    const messagesUpToTick = data?.messages.filter((msg) => {
        if (!currentTick) return false;
        return new Date(msg.timestamp) <= new Date(currentTick.time);
    }) || [];

    const filteredMessages = agentFilter === "all"
        ? messagesUpToTick
        : messagesUpToTick.filter(
            (msg) => msg.from_agent === agentFilter || msg.to_agent === agentFilter
        );

    const handleExport = async () => {
        try {
            await exportGlassBox(sessionId);
        } catch (err) {
            console.error("Failed to export:", err);
        }
    };

    if (loading) {
        return (
            <Card className="border-slate-800 bg-slate-900/50">
                <CardContent className="p-8 flex items-center justify-center">
                    <div className="flex items-center gap-3 text-slate-400">
                        <Activity className="w-5 h-5 animate-pulse" />
                        <span>Loading Glass Box data...</span>
                    </div>
                </CardContent>
            </Card>
        );
    }

    if (error) {
        return (
            <Card className="border-slate-800 bg-slate-900/50">
                <CardContent className="p-8 flex flex-col items-center gap-4">
                    <div className="text-red-400">{error}</div>
                    <Button variant="outline" size="sm" onClick={loadData}>
                        Retry
                    </Button>
                </CardContent>
            </Card>
        );
    }

    if (!data) {
        return (
            <Card className="border-slate-800 bg-slate-900/50">
                <CardContent className="p-8 flex flex-col items-center gap-4">
                    <Eye className="w-8 h-8 text-slate-500" />
                    <div className="text-slate-400 text-center">
                        <p>Glass Box Viewer</p>
                        <p className="text-sm text-slate-500">Visualize agent decision-making in real-time</p>
                    </div>
                    <Button variant="outline" size="sm" onClick={loadData}>
                        Load Session Data
                    </Button>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="border-slate-800 bg-slate-900/50">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-lg">
                        <Eye className="w-5 h-5 text-blue-400" />
                        Glass Box Viewer
                    </CardTitle>
                    <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs text-slate-400">
                            {data.symbol} • {data.mode}
                        </Badge>
                        <Button variant="outline" size="sm" onClick={handleExport}>
                            <Download className="w-4 h-4 mr-1" />
                            Export
                        </Button>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="space-y-4">
                {/* Playback Controls */}
                <div className="flex items-center gap-4 p-3 bg-slate-800/50 rounded-lg">
                    <div className="flex items-center gap-1">
                        <Button variant="ghost" size="sm" onClick={goToStart}>
                            <SkipBack className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={stepBack}>
                            <ChevronRight className="w-4 h-4 rotate-180" />
                        </Button>
                        <Button
                            variant={isPlaying ? "secondary" : "default"}
                            size="sm"
                            onClick={togglePlay}
                        >
                            {isPlaying ? (
                                <Pause className="w-4 h-4" />
                            ) : (
                                <Play className="w-4 h-4" />
                            )}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={stepForward}>
                            <ChevronRight className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={goToEnd}>
                            <SkipForward className="w-4 h-4" />
                        </Button>
                    </div>

                    {/* Progress slider */}
                    <div className="flex-1">
                        <Slider
                            value={[currentTickIndex]}
                            max={data.ticks.length - 1}
                            step={1}
                            onValueChange={([val]) => setCurrentTickIndex(val)}
                            className="cursor-pointer"
                        />
                    </div>

                    {/* Tick counter */}
                    <div className="text-sm font-mono text-slate-400 min-w-[80px] text-right">
                        {currentTickIndex + 1} / {data.ticks.length}
                    </div>

                    {/* Speed control */}
                    <div className="flex items-center gap-2">
                        <FastForward className="w-4 h-4 text-slate-500" />
                        <select
                            value={playbackSpeed}
                            onChange={(e) => setPlaybackSpeed(Number(e.target.value))}
                            className="bg-slate-800 border border-slate-700 rounded text-sm px-2 py-1 text-slate-300"
                        >
                            <option value={0.5}>0.5x</option>
                            <option value={1}>1x</option>
                            <option value={2}>2x</option>
                            <option value={4}>4x</option>
                        </select>
                    </div>
                </div>

                {/* Current Time Display */}
                {currentTick && (
                    <div className="flex items-center gap-4 text-sm">
                        <div className="flex items-center gap-2 text-slate-400">
                            <Clock className="w-4 h-4" />
                            <span className="font-mono">
                                {new Date(currentTick.time).toLocaleString()}
                            </span>
                        </div>
                        <Badge variant="outline" className="text-xs">
                            Tick #{currentTick.tick}
                        </Badge>
                    </div>
                )}

                {/* Main content: Timeline + Messages */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    {/* Timeline (left) */}
                    {showTimeline && (
                        <div className="lg:col-span-1">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium text-slate-300">Timeline</span>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setShowTimeline(false)}
                                    className="text-slate-500"
                                >
                                    Hide
                                </Button>
                            </div>
                            <div className="h-[400px] rounded-lg border border-slate-800 overflow-y-auto">
                                <div className="p-2 space-y-1">
                                    {data.ticks.map((tick, idx) => (
                                        <TickItem
                                            key={tick.tick}
                                            tick={tick}
                                            isActive={idx === currentTickIndex}
                                            onSelect={() => setCurrentTickIndex(idx)}
                                        />
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Messages (right) */}
                    <div className={showTimeline ? "lg:col-span-2" : "lg:col-span-3"}>
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                                <span className="text-sm font-medium text-slate-300">
                                    Messages ({filteredMessages.length})
                                </span>
                                {!showTimeline && (
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setShowTimeline(true)}
                                        className="text-slate-500"
                                    >
                                        Show Timeline
                                    </Button>
                                )}
                            </div>

                            {/* Agent filter */}
                            <div className="flex items-center gap-2">
                                <Filter className="w-4 h-4 text-slate-500" />
                                <select
                                    value={agentFilter}
                                    onChange={(e) => setAgentFilter(e.target.value as AgentRole | "all")}
                                    className="bg-slate-800 border border-slate-700 rounded text-sm px-2 py-1 text-slate-300"
                                >
                                    <option value="all">All Agents</option>
                                    <option value="Trader">Trader</option>
                                    <option value="Main">Main</option>
                                    <option value="Strategy">Strategy</option>
                                    <option value="Worker">Worker</option>
                                </select>
                            </div>
                        </div>

                        <div className="h-[400px] rounded-lg border border-slate-800 overflow-y-auto">
                            <div className="p-2 space-y-2">
                                {filteredMessages.length === 0 ? (
                                    <div className="p-4 text-center text-slate-500 text-sm">
                                        No messages at this point in time
                                    </div>
                                ) : (
                                    filteredMessages.map((msg) => (
                                        <MessageItem
                                            key={msg.id}
                                            message={msg}
                                            isExpanded={expandedMessages.has(msg.id)}
                                            onToggle={() => toggleMessageExpanded(msg.id)}
                                            isHighlighted={
                                                currentTick?.events.some(
                                                    (e) => e.agent === msg.from_agent || e.agent === msg.to_agent
                                                ) || false
                                            }
                                        />
                                    ))
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Session Summary */}
                {data.final_state && (
                    <div className="p-3 bg-slate-800/50 rounded-lg">
                        <div className="flex items-center gap-2 mb-2">
                            <Activity className="w-4 h-4 text-slate-400" />
                            <span className="text-sm font-medium text-slate-300">Session Summary</span>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                            <div>
                                <span className="text-slate-500">Trades</span>
                                <p className="font-mono text-slate-200">{data.final_state.trades_this_session}</p>
                            </div>
                            <div>
                                <span className="text-slate-500">Win Rate</span>
                                <p className="font-mono text-slate-200">{(data.final_state.win_rate * 100).toFixed(1)}%</p>
                            </div>
                            <div>
                                <span className="text-slate-500">Total P&L</span>
                                <p className={`font-mono ${data.final_state.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                                    ${data.final_state.total_pnl.toFixed(2)}
                                </p>
                            </div>
                            <div>
                                <span className="text-slate-500">Final Phase</span>
                                <Badge variant="outline" className="text-xs">
                                    {data.final_state.phase}
                                </Badge>
                            </div>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

export default GlassBoxViewer;
