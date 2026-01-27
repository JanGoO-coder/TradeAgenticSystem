"use client";

import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { sendAIChat, AIChat, StrategySearchResult } from "@/lib/api";
import { Send, Loader2, Bot, User, BookOpen, ChevronDown, ChevronUp } from "lucide-react";

interface Message {
    role: "user" | "assistant";
    content: string;
    suggestions?: string[];
    sources?: StrategySearchResult[];
}

interface ChatPanelProps {
    isOpen: boolean;
    currentContext?: Record<string, unknown>;
}

export function ChatPanel({ isOpen, currentContext }: ChatPanelProps) {
    const [messages, setMessages] = useState<Message[]>([
        {
            role: "assistant",
            content: "Hello! I'm your ICT Trading Assistant, powered by AI with access to the ICT Rulebook.\n\nAsk me about:\n• ICT trading concepts and rules\n• Current market analysis\n• Strategy explanations",
            suggestions: ["Explain Rule 1.1", "What is a kill zone?", "How to identify FVGs?"]
        }
    ]);
    const [input, setInput] = useState("");
    const [showSources, setShowSources] = useState<number | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when new messages arrive
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    // Build conversation history for context
    const getHistory = () => {
        return messages.slice(-10).map(m => ({
            role: m.role,
            content: m.content
        }));
    };

    const chatMutation = useMutation({
        mutationFn: (message: string) => sendAIChat(message, currentContext, getHistory()),
        onSuccess: (data: AIChat) => {
            setMessages((prev) => [
                ...prev,
                {
                    role: "assistant",
                    content: data.message,
                    suggestions: data.suggestions,
                    sources: data.sources
                }
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
        setShowSources(null);
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

                            {/* Sources (RAG references) */}
                            {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                                <div className="ml-8">
                                    <button
                                        onClick={() => setShowSources(showSources === i ? null : i)}
                                        className="flex items-center gap-1 text-[10px] text-purple-400 hover:text-purple-300"
                                    >
                                        <BookOpen className="w-3 h-3" />
                                        {msg.sources.length} source{msg.sources.length > 1 ? 's' : ''}
                                        {showSources === i ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                                    </button>
                                    {showSources === i && (
                                        <div className="mt-1 space-y-1">
                                            {msg.sources.map((source, j) => (
                                                <div key={j} className="text-[10px] bg-slate-800/50 rounded px-2 py-1">
                                                    <div className="text-slate-400">{source.headers}</div>
                                                    {source.rule_ids.length > 0 && (
                                                        <div className="flex gap-1 mt-0.5">
                                                            {source.rule_ids.map((rule, k) => (
                                                                <span key={k} className="px-1 bg-purple-900/50 text-purple-300 rounded">
                                                                    {rule}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    )}
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
