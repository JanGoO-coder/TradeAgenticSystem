"use client";

import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import { getHealth, getSession, analyzeMarket, getDataConfig, TradeSetupResponse, DataConfig, createMT5MarketData, getMT5Status, connectMT5 } from "@/lib/api";
import { Play, Loader2, AlertCircle } from "lucide-react";

export default function Dashboard() {
  const [selectedPair, setSelectedPair] = useState("EURUSD");
  const [currentSetup, setCurrentSetup] = useState<TradeSetupResponse | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const queryClient = useQueryClient();

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

  // MT5 Status query
  const { data: mt5Status } = useQuery({
    queryKey: ["mt5Status"],
    queryFn: getMT5Status,
    refetchInterval: 10000,
  });

  // Auto-connect to MT5 on page load
  useEffect(() => {
    if (mt5Status?.available && !mt5Status?.connected) {
      connectMT5().then(() => {
        queryClient.invalidateQueries({ queryKey: ["mt5Status"] });
      }).catch(() => {});
    }
  }, [mt5Status?.available, mt5Status?.connected, queryClient]);

  const analyzeMutation = useMutation({
    mutationFn: async () => {
      // Fetch real MT5 data instead of sample data
      const marketData = await createMT5MarketData(selectedPair, dataConfig);
      return analyzeMarket(marketData);
    },
    onSuccess: (data) => {
      setCurrentSetup(data);
      setAnalysisError(null);
    },
    onError: (error: Error) => {
      setAnalysisError(error.message);
    },
  });

  const isMT5Connected = mt5Status?.connected ?? false;

  return (
    <div className="flex flex-col h-full w-full">
      <Header
        mode={health?.mode || "ANALYSIS_ONLY"}
        agentAvailable={health?.agent_available || false}
      />

      <ScrollArea className="flex-1 min-h-0">
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
              disabled={analyzeMutation.isPending || !isMT5Connected}
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

          {/* MT5 Connection Warning */}
          {!isMT5Connected && (
            <div className="mb-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg flex items-center gap-2 text-yellow-400 text-sm">
              <AlertCircle className="w-4 h-4" />
              <span>MT5 not connected. Ensure MetaTrader 5 is running to analyze live market data.</span>
            </div>
          )}

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
