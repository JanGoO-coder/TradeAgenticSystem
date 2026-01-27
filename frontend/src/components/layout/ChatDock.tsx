"use client";

import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { MessageSquare, Send, Loader2, Bot, User } from "lucide-react";
import { sendChatMessage, ChatResponse } from "@/lib/api";

interface Message {
    role: "user" | "assistant";
    content: string;
    suggestions?: string[];
}

export function ChatDock() {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState<Message[]>([
        {
            role: "assistant",
            content: "Hello! I'm your ICT Trading Assistant. Ask me about:\n\n• Current session status\n• ICT rules (1.1, 8.1, etc.)\n• Entry models",
            suggestions: ["What's the current session?", "Explain rule 1.1", "What can you do?"]
        }
    ]);
    const [input, setInput] = useState("");
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    // Chat mutation
    const chatMutation = useMutation({
        mutationFn: sendChatMessage,
        onSuccess: (data: ChatResponse) => {
            setMessages((prev) => [
                ...prev,
                {
                    role: "assistant",
                    content: data.message,
                    suggestions: data.suggestions
                }
            ]);
        },
        onError: (error: Error) => {
            setMessages((prev) => [
                ...prev,
                {
                    role: "assistant",
                    content: `Sorry, I encountered an error: ${error.message}`,
                    suggestions: ["Try again", "What can you do?"]
                }
            ]);
        },
    });

    const handleSend = (messageText?: string) => {
        const text = messageText || input;
        if (!text.trim()) return;

        // Add user message
        setMessages((prev) => [...prev, { role: "user", content: text }]);
        setInput("");

        // Send to API
        chatMutation.mutate(text);
    };

    const handleSuggestionClick = (suggestion: string) => {
        handleSend(suggestion);
    };

    return (
        <Sheet open={isOpen} onOpenChange={setIsOpen}>
            <SheetTrigger asChild>
                <Button
                    className="fixed bottom-6 right-6 h-14 w-14 rounded-full shadow-lg bg-emerald-600 hover:bg-emerald-700 z-50"
                    size="icon"
                >
                    <MessageSquare className="w-6 h-6" />
                </Button>
            </SheetTrigger>
            <SheetContent className="w-[400px] sm:w-[540px] bg-slate-950 border-slate-800 flex flex-col">
                <SheetHeader className="border-b border-slate-800 pb-4">
                    <SheetTitle className="text-slate-100 flex items-center gap-2">
                        <Bot className="w-5 h-5 text-emerald-400" />
                        ICT Trading Assistant
                    </SheetTitle>
                </SheetHeader>

                <div className="flex flex-col flex-1 min-h-0">
                    {/* Messages */}
                    <div className="flex-1 pr-4 mt-4 overflow-y-auto" ref={scrollRef}>
                        <div className="space-y-4 pb-4">
                            {messages.map((msg, i) => (
                                <div key={i} className="space-y-2">
                                    <div className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                                        <div className={`flex gap-2 max-w-[90%] ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                                            {/* Avatar */}
                                            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === "user" ? "bg-blue-600" : "bg-slate-800"
                                                }`}>
                                                {msg.role === "user" ? (
                                                    <User className="w-4 h-4 text-white" />
                                                ) : (
                                                    <Bot className="w-4 h-4 text-emerald-400" />
                                                )}
                                            </div>

                                            {/* Message */}
                                            <div
                                                className={`rounded-lg px-4 py-3 text-sm ${msg.role === "user"
                                                        ? "bg-blue-600 text-white"
                                                        : "bg-slate-800 text-slate-100"
                                                    }`}
                                            >
                                                <div className="whitespace-pre-wrap">{msg.content}</div>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Suggestions */}
                                    {msg.role === "assistant" && msg.suggestions && msg.suggestions.length > 0 && i === messages.length - 1 && (
                                        <div className="flex flex-wrap gap-2 ml-10">
                                            {msg.suggestions.map((suggestion, j) => (
                                                <Button
                                                    key={j}
                                                    variant="outline"
                                                    size="sm"
                                                    className="text-xs border-slate-700 text-slate-400 hover:text-slate-100 hover:bg-slate-800"
                                                    onClick={() => handleSuggestionClick(suggestion)}
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
                                        <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center">
                                            <Bot className="w-4 h-4 text-emerald-400" />
                                        </div>
                                        <div className="bg-slate-800 rounded-lg px-4 py-3">
                                            <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Input */}
                    <div className="border-t border-slate-800 pt-4 mt-auto">
                        <div className="flex gap-2">
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => e.key === "Enter" && !chatMutation.isPending && handleSend()}
                                placeholder="Ask about rules, sessions, or setups..."
                                disabled={chatMutation.isPending}
                                className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-emerald-500 disabled:opacity-50"
                            />
                            <Button
                                size="icon"
                                onClick={() => handleSend()}
                                disabled={chatMutation.isPending || !input.trim()}
                                className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50"
                            >
                                {chatMutation.isPending ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    <Send className="w-4 h-4" />
                                )}
                            </Button>
                        </div>
                    </div>
                </div>
            </SheetContent>
        </Sheet>
    );
}
