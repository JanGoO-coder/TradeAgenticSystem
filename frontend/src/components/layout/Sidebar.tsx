"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
    LayoutDashboard,
    Activity,
    History,
    Settings,
    MessageSquare,
    BookOpen,
    LineChart,
    Bot,
    ChevronLeft,
    ChevronRight,
} from "lucide-react";

const navItems = [
    { href: "/", label: "Dashboard", icon: LayoutDashboard },
    { href: "/monitor", label: "Live Monitor", icon: Activity },
    { href: "/history", label: "History", icon: History },
    { href: "/backtest", label: "Backtest", icon: LineChart },
    { href: "/agent-backtest", label: "Agent Backtest", icon: Bot },
    { href: "/rules", label: "Rules", icon: BookOpen },
    { href: "/settings", label: "Settings", icon: Settings },
];

const SIDEBAR_COLLAPSED_KEY = "sidebar-collapsed";

export function Sidebar() {
    const pathname = usePathname();
    const [collapsed, setCollapsed] = useState(false);

    // Load collapsed state from localStorage on mount
    useEffect(() => {
        const saved = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
        if (saved !== null) {
            setCollapsed(saved === "true");
        }
    }, []);

    // Save collapsed state to localStorage
    const toggleCollapsed = () => {
        const newState = !collapsed;
        setCollapsed(newState);
        localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(newState));
    };

    return (
        <aside
            className={cn(
                "hidden lg:flex flex-col border-r border-slate-800 bg-slate-950 transition-all duration-300",
                collapsed ? "w-16" : "w-64"
            )}
        >
            {/* Logo */}
            <div className="h-16 flex items-center px-4 border-b border-slate-800">
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center flex-shrink-0">
                        <span className="text-white font-bold text-sm">ICT</span>
                    </div>
                    {!collapsed && (
                        <span className="font-semibold text-slate-100 whitespace-nowrap">
                            Trading Agent
                        </span>
                    )}
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-2 space-y-1">
                {navItems.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            title={collapsed ? item.label : undefined}
                            className={cn(
                                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                                isActive
                                    ? "bg-slate-800 text-emerald-400"
                                    : "text-slate-400 hover:text-slate-100 hover:bg-slate-900",
                                collapsed && "justify-center px-2"
                            )}
                        >
                            <item.icon className="w-5 h-5 flex-shrink-0" />
                            {!collapsed && <span>{item.label}</span>}
                        </Link>
                    );
                })}
            </nav>

            {/* Chat Toggle */}
            <div className="p-2 border-t border-slate-800">
                <button
                    title={collapsed ? "Open Chat" : undefined}
                    className={cn(
                        "flex items-center gap-3 px-3 py-2 w-full rounded-lg text-sm text-slate-400 hover:text-slate-100 hover:bg-slate-900 transition-colors",
                        collapsed && "justify-center px-2"
                    )}
                >
                    <MessageSquare className="w-5 h-5 flex-shrink-0" />
                    {!collapsed && <span>Open Chat</span>}
                </button>
            </div>

            {/* Collapse Toggle */}
            <div className="p-2 border-t border-slate-800">
                <button
                    onClick={toggleCollapsed}
                    className={cn(
                        "flex items-center gap-3 px-3 py-2 w-full rounded-lg text-sm text-slate-400 hover:text-slate-100 hover:bg-slate-900 transition-colors",
                        collapsed && "justify-center px-2"
                    )}
                    title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                >
                    {collapsed ? (
                        <ChevronRight className="w-5 h-5 flex-shrink-0" />
                    ) : (
                        <>
                            <ChevronLeft className="w-5 h-5 flex-shrink-0" />
                            <span>Collapse</span>
                        </>
                    )}
                </button>
            </div>
        </aside>
    );
}
