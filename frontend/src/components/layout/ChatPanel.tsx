"use client";

import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { sendChatMessage, ChatResponse } from "@/lib/api";
import { Send, Loader2, Bot, User } from "lucide-react";

interface Message {
    role: "user" | "assistant";
    content: string;
    suggestions?: string[];
}

interface ChatPanelProps {
    isOpen: boolean;
}

export function ChatPanel({ isOpen }: ChatPanelProps) {
    const [messages, setMessages] = useState<Message[]>([
        {
            role: "assistant",
            content: "Hello! I'm your ICT Trading Assistant. Ask me about:\n\n• Current session status\n• ICT rules (1.1, 8.1, etc.)\n• Entry models",
            suggestions: ["What's the current session?", "Explain rule 1.1", "What can you do?"]
        }
    ]);
    const [input, setInput] = useState("");
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when new messages arrive
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const chatMutation = useMutation({
        mutationFn: sendChatMessage,
        onSuccess: (data: ChatResponse) => {
            setMessages((prev) => [
                ...prev,
                { role: "assistant", content: data.message, suggestions: data.suggestions }
            ]);
        },
        onError: (error: Error) => {
            setMessages((prev) => [
                ...prev,
                { role: "assistant", content: `Error: ${error.message}`, suggestions: ["Try again"] }
            ]);
        },
    });

    const handleSend = (messageText?: string) => {
        const text = messageText || input;
        if (!text.trim()) return;
        setMessages((prev) => [...prev, { role: "user", content: text }]);
        setInput("");
        chatMutation.mutate(text);
    };

    if (!isOpen) return null;

    return (
        <div className="flex flex-col h-full">
            {/* Scrollable Messages Area */}
            <div className="flex-1 overflow-y-auto p-3">
                <div className="space-y-3">
                    {messages.map((msg, i) => (
                        <div key={i} className="space-y-2">
                            <div className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                                <div className={`flex gap-2 max-w-[90%] ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                                    <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === "user" ? "bg-blue-600" : "bg-slate-800"
                                        }`}>
                                        {msg.role === "user" ? (
                                            <User className="w-3 h-3 text-white" />
                                        ) : (
                                            <Bot className="w-3 h-3 text-emerald-400" />
                                        )}
                                    </div>
                                    <div className={`rounded-lg px-3 py-2 text-sm ${msg.role === "user"
                                            ? "bg-blue-600 text-white"
                                            : "bg-slate-800 text-slate-100"
                                        }`}>
                                        <div className="whitespace-pre-wrap break-words text-xs">{msg.content}</div>
                                    </div>
                                </div>
                            </div>

                            {/* Suggestions */}
                            {msg.role === "assistant" && msg.suggestions && msg.suggestions.length > 0 && i === messages.length - 1 && (
                                <div className="flex flex-wrap gap-1 ml-8">
                                    {msg.suggestions.map((suggestion, j) => (
                                        <Button
                                            key={j}
                                            variant="outline"
                                            size="sm"
                                            className="text-[10px] h-6 px-2 border-slate-700 text-slate-400 hover:text-slate-100 hover:bg-slate-800"
                                            onClick={() => handleSend(suggestion)}
                                        >
                                            {suggestion}
                                        </Button>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}

                    {/* Loading indicator */}
                    {chatMutation.isPending && (
                        <div className="flex justify-start">
                            <div className="flex gap-2">
                                <div className="w-6 h-6 rounded-full bg-slate-800 flex items-center justify-center">
                                    <Bot className="w-3 h-3 text-emerald-400" />
                                </div>
                                <div className="bg-slate-800 rounded-lg px-3 py-2">
                                    <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Scroll anchor */}
                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* Fixed Input Area */}
            <div className="flex-shrink-0 p-3 border-t border-slate-800 bg-slate-900/50">
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && !chatMutation.isPending && handleSend()}
                        placeholder="Ask anything..."
                        disabled={chatMutation.isPending}
                        className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-emerald-500"
                    />
                    <Button
                        size="icon"
                        onClick={() => handleSend()}
                        disabled={chatMutation.isPending || !input.trim()}
                        className="bg-emerald-600 hover:bg-emerald-700 h-8 w-8"
                    >
                        {chatMutation.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                    </Button>
                </div>
            </div>
        </div>
    );
}
