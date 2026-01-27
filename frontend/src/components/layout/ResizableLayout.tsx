"use client";

import { useState } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { ChatPanel } from "@/components/layout/ChatPanel";
import { Button } from "@/components/ui/button";
import { MessageSquare, X } from "lucide-react";

interface ResizableLayoutProps {
  children: React.ReactNode;
}

export function ResizableLayout({ children }: ResizableLayoutProps) {
  const [isChatOpen, setIsChatOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 overflow-auto">
          {children}
        </div>

        {/* Chat Panel - Fixed width side panel */}
        {isChatOpen && (
          <div className="w-[350px] flex-shrink-0 flex flex-col h-full bg-slate-950 border-l border-slate-800">
            {/* Chat Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-900/50">
              <span className="text-sm font-medium text-slate-300">AI Assistant</span>
              <Button
                onClick={() => setIsChatOpen(false)}
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-slate-400 hover:text-slate-100"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>

            {/* Chat Content */}
            <div className="flex-1 overflow-hidden">
              <ChatPanel isOpen={true} />
            </div>
          </div>
        )}
      </div>

      {/* Chat Toggle Button - only show when closed */}
      {!isChatOpen && (
        <Button
          onClick={() => setIsChatOpen(true)}
          className="fixed bottom-6 right-6 h-12 w-12 rounded-full shadow-lg bg-emerald-600 hover:bg-emerald-700 z-50"
          size="icon"
        >
          <MessageSquare className="w-5 h-5" />
        </Button>
      )}
    </div>
  );
}