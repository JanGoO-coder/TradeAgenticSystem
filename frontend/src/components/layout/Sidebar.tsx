"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
    LayoutDashboard,
    Activity,
    History,
    Settings,
    MessageSquare,
    BookOpen,
    FlaskConical,
    Eye,
    ChevronLeft,
    ChevronRight,
} from "lucide-react";

const navItems = [
    { href: "/", label: "Dashboard", icon: LayoutDashboard },
    { href: "/monitor", label: "Live Monitor", icon: Activity },
    { href: "/backtest", label: "Backtest", icon: FlaskConical },
    { href: "/replay", label: "Glass Box", icon: Eye },
    { href: "/history", label: "History", icon: History },
    { href: "/rules", label: "Rules", icon: BookOpen },
    { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
    const pathname = usePathname();
    const [isCollapsed, setIsCollapsed] = useState(false);

    return (
        <aside
            className={cn(
                "hidden lg:flex flex-col border-r border-slate-800 bg-slate-950 transition-all duration-300 ease-in-out",
                isCollapsed ? "w-20" : "w-64"
            )}
        >
            {/* Logo */}
            <div className={cn(
                "h-16 flex items-center border-b border-slate-800 transition-all duration-300",
                isCollapsed ? "justify-center px-0" : "px-6 justify-between"
            )}>
                {!isCollapsed && (
                    <div className="flex items-center gap-2 overflow-hidden whitespace-nowrap">
                        <Image
                            src="/logo-dark.svg"
                            alt="Trading Agent"
                            width={140}
                            height={40}
                            className="h-6 w-auto"
                            priority
                        />
                    </div>
                )}
                {isCollapsed && (
                    <div className="flex items-center justify-center">
                        <Image
                            src="/logo-dark.svg"
                            alt="Trading Agent"
                            width={32}
                            height={32}
                            className="h-8 w-8 object-contain"
                            priority
                        />
                    </div>
                )}

                <button
                    onClick={() => setIsCollapsed(!isCollapsed)}
                    className={cn(
                        "text-slate-400 hover:text-white transition-colors p-1 rounded-md hover:bg-slate-900",
                        isCollapsed ? "hidden" : "block"
                    )}
                >
                    <ChevronLeft className="w-5 h-5" />
                </button>
            </div>

            {/* Toggle Button for Collapsed State - Shown in Nav area or separate */}
            {isCollapsed && (
                <div className="flex justify-center py-4 border-b border-slate-800">
                    <button
                        onClick={() => setIsCollapsed(!isCollapsed)}
                        className="text-slate-400 hover:text-white transition-colors p-1 rounded-md hover:bg-slate-900"
                    >
                        <ChevronRight className="w-5 h-5" />
                    </button>
                </div>
            )}

            {/* Navigation */}
            <nav className="flex-1 p-3 space-y-1 overflow-y-auto overflow-x-hidden">
                {navItems.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={cn(
                                "flex items-center rounded-lg transition-colors relative group",
                                isCollapsed
                                    ? "justify-center p-2"
                                    : "gap-3 px-3 py-2",
                                isActive
                                    ? "bg-slate-800 text-emerald-400"
                                    : "text-slate-400 hover:text-slate-100 hover:bg-slate-900"
                            )}
                            title={isCollapsed ? item.label : undefined}
                        >
                            <item.icon className={cn("flex-shrink-0", isCollapsed ? "w-6 h-6" : "w-5 h-5")} />

                            {!isCollapsed && (
                                <span className="text-sm whitespace-nowrap overflow-hidden text-ellipsis">
                                    {item.label}
                                </span>
                            )}

                            {/* Tooltip for collapsed state */}
                            {isCollapsed && (
                                <div className="absolute left-full top-1/2 -translate-y-1/2 ml-2 px-2 py-1 bg-slate-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 shadow-lg border border-slate-700">
                                    {item.label}
                                </div>
                            )}
                        </Link>
                    );
                })}
            </nav>

            {/* Chat Toggle */}
            <div className={cn(
                "border-t border-slate-800 transition-all",
                isCollapsed ? "p-2" : "p-4"
            )}>
                <button className={cn(
                    "flex items-center rounded-lg transition-colors text-slate-400 hover:text-slate-100 hover:bg-slate-900",
                    isCollapsed ? "justify-center w-full p-2" : "gap-3 px-3 py-2 w-full text-sm"
                )}>
                    <MessageSquare className={cn("flex-shrink-0", isCollapsed ? "w-6 h-6" : "w-5 h-5")} />
                    {!isCollapsed && <span>Open Chat</span>}
                </button>
            </div>
        </aside>
    );
}
