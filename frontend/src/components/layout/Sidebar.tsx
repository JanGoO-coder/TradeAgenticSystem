"use client";

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
} from "lucide-react";

const navItems = [
    { href: "/", label: "Dashboard", icon: LayoutDashboard },
    { href: "/monitor", label: "Live Monitor", icon: Activity },
    { href: "/history", label: "History", icon: History },
    { href: "/rules", label: "Rules", icon: BookOpen },
    { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
    const pathname = usePathname();

    return (
        <aside className="hidden lg:flex flex-col w-64 border-r border-slate-800 bg-slate-950">
            {/* Logo */}
            <div className="h-16 flex items-center px-6 border-b border-slate-800">
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center">
                        <span className="text-white font-bold text-sm">ICT</span>
                    </div>
                    <span className="font-semibold text-slate-100">Trading Agent</span>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-4 space-y-1">
                {navItems.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={cn(
                                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                                isActive
                                    ? "bg-slate-800 text-emerald-400"
                                    : "text-slate-400 hover:text-slate-100 hover:bg-slate-900"
                            )}
                        >
                            <item.icon className="w-5 h-5" />
                            {item.label}
                        </Link>
                    );
                })}
            </nav>

            {/* Chat Toggle */}
            <div className="p-4 border-t border-slate-800">
                <button className="flex items-center gap-3 px-3 py-2 w-full rounded-lg text-sm text-slate-400 hover:text-slate-100 hover:bg-slate-900 transition-colors">
                    <MessageSquare className="w-5 h-5" />
                    Open Chat
                </button>
            </div>
        </aside>
    );
}
