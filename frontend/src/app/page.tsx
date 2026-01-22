"use client";

import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import { SessionClock } from "@/components/dashboard/SessionClock";
import { BiasCard } from "@/components/dashboard/BiasCard";
import { SetupCard } from "@/components/dashboard/SetupCard";
import { ChecklistPanel } from "@/components/dashboard/ChecklistPanel";
import { ConfluenceMeter } from "@/components/dashboard/ConfluenceMeter";
import { TradingPairSelector } from "@/components/dashboard/TradingPairSelector";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { getHealth, getSession, analyzeMarket, getDataConfig, TradeSetupResponse, DataConfig } from "@/lib/api";
import { Play, Loader2 } from "lucide-react";

// Generate sample market data that varies by symbol and uses config
const createSampleMarketData = (symbol: string, config?: DataConfig) => {
  // Use symbol to create consistent but different data per pair
  const seed = symbol.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const basePrice = symbol.includes('JPY') ? 150.0 : symbol.includes('XAU') ? 2000.0 : symbol.includes('BTC') ? 45000.0 : 1.08;
  const volatility = symbol.includes('XAU') ? 0.005 : symbol.includes('BTC') ? 0.02 : 0.002;

  // Use config bar counts or defaults
  const htfBars = config?.htf_bars || 50;
  const ltfBars = config?.ltf_bars || 100;
  const microBars = config?.micro_bars || 50;

  // Generate varying OHLC based on symbol
  const generateBars = (count: number, tf: string) => {
    const bars = [];
    let price = basePrice;
    const trendDirection = (seed % 3) - 1; // -1, 0, or 1

    for (let i = 0; i < count; i++) {
      const change = (Math.sin(seed + i) * volatility) + (trendDirection * volatility * 0.3);
      const high = price * (1 + Math.abs(change) + volatility * 0.5);
      const low = price * (1 - Math.abs(change) - volatility * 0.5);
      const close = price * (1 + change);

      bars.push({
        timestamp: new Date(Date.now() - (count - i) * (tf === "1H" ? 3600000 : tf === "15M" ? 900000 : 300000)).toISOString(),
        open: Number(price.toFixed(5)),
        high: Number(high.toFixed(5)),
        low: Number(low.toFixed(5)),
        close: Number(close.toFixed(5)),
        volume: 1000 + (seed % 500) + i * 100
      });

      price = close;
    }
    return bars;
  };

  return {
    symbol,
    timestamp: new Date().toISOString(),
    timeframe_bars: {
      "1H": generateBars(htfBars, "1H"),
      "15M": generateBars(ltfBars, "15M"),
      "5M": generateBars(microBars, "5M")
    },
    account_balance: 10000.0,
    risk_pct: 1.0,
    economic_calendar: []
  };
};

export default function Dashboard() {
  const [selectedPair, setSelectedPair] = useState("EURUSD");
  const [currentSetup, setCurrentSetup] = useState<TradeSetupResponse | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  // Clear analysis when pair changes
  useEffect(() => {
    setCurrentSetup(null);
    setAnalysisError(null);
  }, [selectedPair]);

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 5000,
  });

  const { data: session } = useQuery({
    queryKey: ["session"],
    queryFn: getSession,
    refetchInterval: 1000,
  });

  const { data: dataConfig } = useQuery({
    queryKey: ["dataConfig"],
    queryFn: getDataConfig,
    staleTime: 30000,
  });

  const analyzeMutation = useMutation({
    mutationFn: () => analyzeMarket(createSampleMarketData(selectedPair, dataConfig)),
    onSuccess: (data) => {
      setCurrentSetup(data);
      setAnalysisError(null);
    },
    onError: (error: Error) => {
      setAnalysisError(error.message);
    },
  });

  return (
    <div className="flex flex-col h-full w-full overflow-hidden">
      <Header
        mode={health?.mode || "ANALYSIS_ONLY"}
        agentAvailable={health?.agent_available || false}
      />

      <ScrollArea className="flex-1">
        <div className="p-4 min-w-0">
          {/* Quick Actions */}
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-lg font-semibold text-slate-100">Dashboard</h2>
              <TradingPairSelector
                value={selectedPair}
                onChange={setSelectedPair}
                className="w-[160px]"
              />
            </div>
            <Button
              onClick={() => analyzeMutation.mutate()}
              className="bg-emerald-600 hover:bg-emerald-700"
              disabled={analyzeMutation.isPending}
              size="sm"
            >
              {analyzeMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Analyze {selectedPair}
                </>
              )}
            </Button>
          </div>

          {/* Current Analysis Info */}
          {currentSetup && (
            <div className="mb-4 p-2 bg-slate-800/50 rounded-lg border border-slate-700 flex items-center gap-2">
              <span className="text-xs text-slate-400">Analyzing:</span>
              <span className="text-sm font-medium text-emerald-400">{currentSetup.symbol}</span>
              <span className="text-xs text-slate-500">•</span>
              <span className="text-xs text-slate-400">{new Date(currentSetup.timestamp).toLocaleTimeString()}</span>
            </div>
          )}

          {/* Error Display */}
          {analysisError && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              Error: {analysisError}
            </div>
          )}

          {/* Main Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {/* Left Column */}
            <div className="space-y-4">
              <SessionClock
                session={session?.session || "Loading..."}
                killZoneActive={session?.kill_zone_active || false}
                killZoneName={session?.kill_zone_name || null}
                currentTimeEst={session?.current_time_est || "00:00"}
              />
              <BiasCard
                bias={currentSetup?.htf_bias.value || "NEUTRAL"}
                ruleRefs={currentSetup?.htf_bias.rule_refs || ["1.1"]}
                timeframe="1H"
              />
              <BiasCard
                bias={
                  currentSetup?.ltf_alignment.alignment === "ALIGNED"
                    ? currentSetup.htf_bias.value
                    : "NEUTRAL"
                }
                ruleRefs={currentSetup?.ltf_alignment.rule_refs || ["1.2"]}
                timeframe="15M"
              />
            </div>

            {/* Middle Column */}
            <div className="space-y-4">
              <SetupCard setup={currentSetup} />
              <ConfluenceMeter
                score={currentSetup?.setup.confluence_score || 0}
                confidence={currentSetup?.confidence || 0}
              />
            </div>

            {/* Right Column */}
            <div className="space-y-4 md:col-span-2 xl:col-span-1">
              <ChecklistPanel checklist={currentSetup?.checklist || null} />

              {/* Agent Nodes */}
              <Card className="bg-slate-900 border-slate-800">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-slate-400">
                    Agent Pipeline
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {(currentSetup?.graph_nodes_triggered || []).map((node) => (
                      <span
                        key={node}
                        className="px-2 py-1 text-xs bg-emerald-500/10 text-emerald-400 rounded-md border border-emerald-500/30"
                      >
                        {node}
                      </span>
                    ))}
                    {!currentSetup && (
                      <span className="text-sm text-slate-500">
                        Select a pair and click Analyze
                      </span>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Explanation */}
              {currentSetup && (
                <Card className="bg-slate-900 border-slate-800">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-slate-400">
                      Explanation
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-slate-300 leading-relaxed">
                      {currentSetup.explanation}
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
