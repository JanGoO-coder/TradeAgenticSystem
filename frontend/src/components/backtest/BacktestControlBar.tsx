"use client";

import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import {
    Play,
    Pause,
    SkipForward,
    SkipBack,
    RotateCcw,
    Loader2,
    ChevronLeft,
    ChevronRight,
    FastForward,
    Rewind,
} from "lucide-react";

interface BacktestControlBarProps {
    isLoaded: boolean;
    isPlaying: boolean;
    currentIndex: number;
    totalBars: number;
    progress: number;
    speed: number;
    currentTimestamp?: string;
    onPlay: () => void;
    onPause: () => void;
    onStepForward: (bars: number) => void;
    onStepBack: (bars: number) => void;
    onReset: () => void;
    onJumpTo: (index: number) => void;
    onSpeedChange: (speed: number) => void;
    isSteppingForward?: boolean;
    isSteppingBack?: boolean;
    isResetting?: boolean;
}

const speedOptions = [
    { value: 1, label: "1x" },
    { value: 2, label: "2x" },
    { value: 5, label: "5x" },
    { value: 10, label: "10x" },
    { value: 25, label: "25x" },
];

export function BacktestControlBar({
    isLoaded,
    isPlaying,
    currentIndex,
    totalBars,
    progress,
    speed,
    currentTimestamp,
    onPlay,
    onPause,
    onStepForward,
    onStepBack,
    onReset,
    onJumpTo,
    onSpeedChange,
    isSteppingForward = false,
    isSteppingBack = false,
    isResetting = false,
}: BacktestControlBarProps) {
    const formatTimestamp = (ts?: string) => {
        if (!ts) return "--";
        try {
            return new Date(ts).toLocaleString("en-US", {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
            });
        } catch {
            return ts;
        }
    };

    return (
        <div className="bg-slate-900 border-t border-slate-800 px-4 py-2">
            <div className="flex items-center gap-4">
                {/* Progress Slider */}
                <div className="flex-1 flex items-center gap-3">
                    <span className="text-xs text-slate-500 w-12 text-right font-mono">
                        {currentIndex}
                    </span>
                    <div className="flex-1 relative">
                        <Slider
                            value={[currentIndex]}
                            min={0}
                            max={Math.max(totalBars - 1, 1)}
                            step={1}
                            disabled={!isLoaded}
                            onValueChange={([val]) => onJumpTo(val)}
                            className="w-full"
                        />
                        {/* Progress overlay */}
                        <div className="absolute top-1/2 left-0 right-0 h-1 -translate-y-1/2 pointer-events-none">
                            <div 
                                className="h-full bg-gradient-to-r from-blue-500/30 to-emerald-500/30 rounded-full"
                                style={{ width: `${progress}%` }}
                            />
                        </div>
                    </div>
                    <span className="text-xs text-slate-500 w-12 font-mono">
                        {totalBars}
                    </span>
                </div>

                {/* Timestamp Display */}
                <div className="w-36 text-center">
                    <span className="text-xs text-slate-400 font-mono">
                        {formatTimestamp(currentTimestamp)}
                    </span>
                </div>

                {/* Control Buttons */}
                <div className="flex items-center gap-1">
                    {/* Reset */}
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={onReset}
                        disabled={!isLoaded || isResetting}
                        className="h-8 w-8 text-slate-400 hover:text-slate-100"
                        title="Reset (Home)"
                    >
                        {isResetting ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                            <RotateCcw className="w-4 h-4" />
                        )}
                    </Button>

                    {/* Step back 5 */}
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onStepBack(5)}
                        disabled={!isLoaded || isSteppingBack || currentIndex === 0}
                        className="h-8 w-8 text-slate-400 hover:text-slate-100"
                        title="Back 5 bars (Shift+←)"
                    >
                        <Rewind className="w-4 h-4" />
                    </Button>

                    {/* Step back 1 */}
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onStepBack(1)}
                        disabled={!isLoaded || isSteppingBack || currentIndex === 0}
                        className="h-8 w-8 text-slate-400 hover:text-slate-100"
                        title="Back 1 bar (←)"
                    >
                        {isSteppingBack ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                            <SkipBack className="w-4 h-4" />
                        )}
                    </Button>

                    {/* Play/Pause */}
                    <Button
                        size="sm"
                        onClick={isPlaying ? onPause : onPlay}
                        disabled={!isLoaded}
                        className={`h-8 w-16 ${
                            isPlaying 
                                ? "bg-yellow-600 hover:bg-yellow-700" 
                                : "bg-emerald-600 hover:bg-emerald-700"
                        }`}
                        title="Play/Pause (Space)"
                    >
                        {isPlaying ? (
                            <Pause className="w-4 h-4" />
                        ) : (
                            <Play className="w-4 h-4" />
                        )}
                    </Button>

                    {/* Step forward 1 */}
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onStepForward(1)}
                        disabled={!isLoaded || isSteppingForward || currentIndex >= totalBars - 1}
                        className="h-8 w-8 text-slate-400 hover:text-slate-100"
                        title="Forward 1 bar (→)"
                    >
                        {isSteppingForward ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                            <SkipForward className="w-4 h-4" />
                        )}
                    </Button>

                    {/* Step forward 5 */}
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onStepForward(5)}
                        disabled={!isLoaded || isSteppingForward || currentIndex >= totalBars - 1}
                        className="h-8 w-8 text-slate-400 hover:text-slate-100"
                        title="Forward 5 bars (Shift+→)"
                    >
                        <FastForward className="w-4 h-4" />
                    </Button>
                </div>

                {/* Speed Selector */}
                <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">Speed:</span>
                    <Select
                        value={String(speed)}
                        onValueChange={(v) => onSpeedChange(parseInt(v))}
                    >
                        <SelectTrigger className="w-16 h-7 bg-slate-800 border-slate-700 text-xs">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {speedOptions.map((opt) => (
                                <SelectItem key={opt.value} value={String(opt.value)}>
                                    {opt.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                {/* Progress Badge */}
                <Badge 
                    variant="outline" 
                    className="bg-slate-800 border-slate-700 text-slate-300 font-mono text-xs"
                >
                    {progress.toFixed(1)}%
                </Badge>
            </div>
        </div>
    );
}
