"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Clock, Zap } from "lucide-react";

interface SessionClockProps {
    session: string;
    killZoneActive: boolean;
    killZoneName: string | null;
    currentTimeEst: string;
}

export function SessionClock({
    session,
    killZoneActive,
    killZoneName,
    currentTimeEst,
}: SessionClockProps) {
    const [time, setTime] = useState(currentTimeEst);

    useEffect(() => {
        const interval = setInterval(() => {
            const now = new Date();
            const estHour = (now.getUTCHours() - 5 + 24) % 24;
            const estMin = now.getUTCMinutes();
            const estSec = now.getUTCSeconds();
            setTime(`${estHour.toString().padStart(2, "0")}:${estMin.toString().padStart(2, "0")}:${estSec.toString().padStart(2, "0")}`);
        }, 1000);
        return () => clearInterval(interval);
    }, []);

    const getSessionColor = (session: string) => {
        switch (session) {
            case "London":
                return "text-blue-400";
            case "NY":
                return "text-orange-400";
            case "Asia":
                return "text-purple-400";
            default:
                return "text-slate-400";
        }
    };

    return (
        <Card className="bg-slate-900 border-slate-800">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-slate-400 flex items-center gap-2">
                    <Clock className="w-4 h-4" />
                    Session Clock
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-3">
                    {/* Time Display */}
                    <div className="text-3xl font-mono font-bold text-slate-100">
                        {time} <span className="text-sm text-slate-500">EST</span>
                    </div>

                    {/* Session Badge */}
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-slate-400">Session:</span>
                        <span className={`font-semibold ${getSessionColor(session)}`}>
                            {session}
                        </span>
                    </div>

                    {/* Kill Zone Status */}
                    <div className="flex items-center gap-2">
                        {killZoneActive ? (
                            <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/50 flex items-center gap-1">
                                <Zap className="w-3 h-3" />
                                {killZoneName} Kill Zone Active
                            </Badge>
                        ) : (
                            <Badge variant="outline" className="text-slate-500 border-slate-700">
                                Outside Kill Zone
                            </Badge>
                        )}
                    </div>

                    {/* Kill Zone Schedule */}
                    <div className="text-xs text-slate-500 space-y-1">
                        <div className="flex justify-between">
                            <span>London KZ:</span>
                            <span>02:00 - 05:00 EST</span>
                        </div>
                        <div className="flex justify-between">
                            <span>NY KZ:</span>
                            <span>07:00 - 10:00 EST</span>
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
