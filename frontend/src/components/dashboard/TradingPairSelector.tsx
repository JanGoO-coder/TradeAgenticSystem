"use client";

import { useMemo } from "react";
import {
    Select,
    SelectContent,
    SelectGroup,
    SelectItem,
    SelectLabel,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

const tradingPairs = {
    forex: [
        { value: "EURUSD", label: "EUR/USD" },
        { value: "GBPUSD", label: "GBP/USD" },
        { value: "USDJPY", label: "USD/JPY" },
        { value: "USDCHF", label: "USD/CHF" },
        { value: "AUDUSD", label: "AUD/USD" },
        { value: "USDCAD", label: "USD/CAD" },
        { value: "NZDUSD", label: "NZD/USD" },
        { value: "EURGBP", label: "EUR/GBP" },
        { value: "EURJPY", label: "EUR/JPY" },
        { value: "GBPJPY", label: "GBP/JPY" },
    ],
    commodities: [
        { value: "XAUUSD", label: "Gold (XAU/USD)" },
        { value: "XAGUSD", label: "Silver (XAG/USD)" },
        { value: "USOIL", label: "Crude Oil (WTI)" },
        { value: "UKOIL", label: "Brent Oil" },
        { value: "XPTUSD", label: "Platinum" },
    ],
    indices: [
        { value: "US30", label: "Dow Jones 30" },
        { value: "US500", label: "S&P 500" },
        { value: "US100", label: "Nasdaq 100" },
        { value: "GER40", label: "DAX 40" },
        { value: "UK100", label: "FTSE 100" },
    ],
    crypto: [
        { value: "BTCUSD", label: "Bitcoin (BTC/USD)" },
        { value: "ETHUSD", label: "Ethereum (ETH/USD)" },
    ],
};

// Helper to categorize MT5 symbols
function categorizeSymbols(symbols: string[]): {
    forex: { value: string; label: string }[];
    commodities: { value: string; label: string }[];
    indices: { value: string; label: string }[];
    crypto: { value: string; label: string }[];
    other: { value: string; label: string }[];
} {
    const forexPatterns = /^(EUR|USD|GBP|JPY|CHF|AUD|CAD|NZD)/i;
    const commodityPatterns = /^(XAU|XAG|XPT|XPD|OIL|USOIL|UKOIL|BRENT|WTI)/i;
    const cryptoPatterns = /^(BTC|ETH|LTC|XRP|BNB|SOL|ADA|DOGE)/i;
    const indexPatterns = /^(US30|US500|US100|NAS|SPX|DJI|DAX|GER|UK100|FTSE|JP225|AUS200)/i;

    const result = {
        forex: [] as { value: string; label: string }[],
        commodities: [] as { value: string; label: string }[],
        indices: [] as { value: string; label: string }[],
        crypto: [] as { value: string; label: string }[],
        other: [] as { value: string; label: string }[],
    };

    symbols.forEach((symbol) => {
        const formatted = { value: symbol, label: formatSymbolLabel(symbol) };
        
        if (cryptoPatterns.test(symbol)) {
            result.crypto.push(formatted);
        } else if (commodityPatterns.test(symbol)) {
            result.commodities.push(formatted);
        } else if (indexPatterns.test(symbol)) {
            result.indices.push(formatted);
        } else if (forexPatterns.test(symbol)) {
            result.forex.push(formatted);
        } else {
            result.other.push(formatted);
        }
    });

    return result;
}

// Format symbol for display
function formatSymbolLabel(symbol: string): string {
    // Common symbol name mappings
    const labelMap: Record<string, string> = {
        EURUSD: "EUR/USD",
        GBPUSD: "GBP/USD",
        USDJPY: "USD/JPY",
        USDCHF: "USD/CHF",
        AUDUSD: "AUD/USD",
        USDCAD: "USD/CAD",
        NZDUSD: "NZD/USD",
        EURGBP: "EUR/GBP",
        EURJPY: "EUR/JPY",
        GBPJPY: "GBP/JPY",
        XAUUSD: "Gold (XAU/USD)",
        XAGUSD: "Silver (XAG/USD)",
        BTCUSD: "Bitcoin (BTC/USD)",
        ETHUSD: "Ethereum (ETH/USD)",
    };
    
    return labelMap[symbol] || symbol;
}

interface TradingPairSelectorProps {
    value: string;
    onChange: (value: string) => void;
    className?: string;
    mt5Symbols?: string[];  // Optional MT5 symbols from API
}

export function TradingPairSelector({ 
    value, 
    onChange, 
    className,
    mt5Symbols 
}: TradingPairSelectorProps) {
    
    // Categorize symbols - use MT5 symbols if available, else fallback to defaults
    const categorized = useMemo(() => {
        if (mt5Symbols && mt5Symbols.length > 0) {
            return categorizeSymbols(mt5Symbols);
        }
        return { ...tradingPairs, other: [] };
    }, [mt5Symbols]);

    const hasSymbols = (arr: unknown[]) => arr && arr.length > 0;

    return (
        <Select value={value} onValueChange={onChange}>
            <SelectTrigger className={`bg-slate-800 border-slate-700 text-slate-100 ${className}`}>
                <SelectValue placeholder="Select pair" />
            </SelectTrigger>
            <SelectContent className="bg-slate-900 border-slate-800 max-h-[300px]">
                {hasSymbols(categorized.forex) && (
                    <SelectGroup>
                        <SelectLabel className="text-slate-500 text-xs">Forex</SelectLabel>
                        {categorized.forex.map((pair) => (
                            <SelectItem
                                key={pair.value}
                                value={pair.value}
                                className="text-slate-100 focus:bg-slate-800 focus:text-slate-100"
                            >
                                {pair.label}
                            </SelectItem>
                        ))}
                    </SelectGroup>
                )}
                {hasSymbols(categorized.commodities) && (
                    <SelectGroup>
                        <SelectLabel className="text-slate-500 text-xs">Commodities</SelectLabel>
                        {categorized.commodities.map((pair) => (
                            <SelectItem
                                key={pair.value}
                                value={pair.value}
                                className="text-slate-100 focus:bg-slate-800 focus:text-slate-100"
                            >
                                {pair.label}
                            </SelectItem>
                        ))}
                    </SelectGroup>
                )}
                {hasSymbols(categorized.indices) && (
                    <SelectGroup>
                        <SelectLabel className="text-slate-500 text-xs">Indices</SelectLabel>
                        {categorized.indices.map((pair) => (
                            <SelectItem
                                key={pair.value}
                                value={pair.value}
                                className="text-slate-100 focus:bg-slate-800 focus:text-slate-100"
                            >
                                {pair.label}
                            </SelectItem>
                        ))}
                    </SelectGroup>
                )}
                {hasSymbols(categorized.crypto) && (
                    <SelectGroup>
                        <SelectLabel className="text-slate-500 text-xs">Crypto</SelectLabel>
                        {categorized.crypto.map((pair) => (
                            <SelectItem
                                key={pair.value}
                                value={pair.value}
                                className="text-slate-100 focus:bg-slate-800 focus:text-slate-100"
                            >
                                {pair.label}
                            </SelectItem>
                        ))}
                    </SelectGroup>
                )}
                {hasSymbols(categorized.other) && (
                    <SelectGroup>
                        <SelectLabel className="text-slate-500 text-xs">Other</SelectLabel>
                        {categorized.other.map((pair) => (
                            <SelectItem
                                key={pair.value}
                                value={pair.value}
                                className="text-slate-100 focus:bg-slate-800 focus:text-slate-100"
                            >
                                {pair.label}
                            </SelectItem>
                        ))}
                    </SelectGroup>
                )}
            </SelectContent>
        </Select>
    );
}

export { tradingPairs };
