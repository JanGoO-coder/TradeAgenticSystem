"use client";

import { useState } from "react";
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

interface TradingPairSelectorProps {
    value: string;
    onChange: (value: string) => void;
    className?: string;
}

export function TradingPairSelector({ value, onChange, className }: TradingPairSelectorProps) {
    return (
        <Select value={value} onValueChange={onChange}>
            <SelectTrigger className={`bg-slate-800 border-slate-700 text-slate-100 ${className}`}>
                <SelectValue placeholder="Select pair" />
            </SelectTrigger>
            <SelectContent className="bg-slate-900 border-slate-800">
                <SelectGroup>
                    <SelectLabel className="text-slate-500 text-xs">Forex Majors</SelectLabel>
                    {tradingPairs.forex.map((pair) => (
                        <SelectItem
                            key={pair.value}
                            value={pair.value}
                            className="text-slate-100 focus:bg-slate-800 focus:text-slate-100"
                        >
                            {pair.label}
                        </SelectItem>
                    ))}
                </SelectGroup>
                <SelectGroup>
                    <SelectLabel className="text-slate-500 text-xs">Commodities</SelectLabel>
                    {tradingPairs.commodities.map((pair) => (
                        <SelectItem
                            key={pair.value}
                            value={pair.value}
                            className="text-slate-100 focus:bg-slate-800 focus:text-slate-100"
                        >
                            {pair.label}
                        </SelectItem>
                    ))}
                </SelectGroup>
                <SelectGroup>
                    <SelectLabel className="text-slate-500 text-xs">Indices</SelectLabel>
                    {tradingPairs.indices.map((pair) => (
                        <SelectItem
                            key={pair.value}
                            value={pair.value}
                            className="text-slate-100 focus:bg-slate-800 focus:text-slate-100"
                        >
                            {pair.label}
                        </SelectItem>
                    ))}
                </SelectGroup>
                <SelectGroup>
                    <SelectLabel className="text-slate-500 text-xs">Crypto</SelectLabel>
                    {tradingPairs.crypto.map((pair) => (
                        <SelectItem
                            key={pair.value}
                            value={pair.value}
                            className="text-slate-100 focus:bg-slate-800 focus:text-slate-100"
                        >
                            {pair.label}
                        </SelectItem>
                    ))}
                </SelectGroup>
            </SelectContent>
        </Select>
    );
}

export { tradingPairs };
