"use client";

import React, { useEffect, useState, useCallback } from "react";

// --- Sports Betting Analytics Imports ---
import { SportsHeader } from "@/components/sports/SportsHeader";
import { ValueBetsScanner } from "@/components/sports/ValueBetsScanner";
import { MatchAnalysisModal } from "@/components/sports/MatchAnalysisModal";
import { OddsComparisonWidget } from "@/components/sports/OddsComparisonWidget";
import { InsiderFeedWidget } from "@/components/sports/InsiderFeedWidget";
import { BankrollTracker } from "@/components/sports/BankrollTracker";

import {
  fetchSportsMatches,
  syncOdds,
  fetchValueBets,
  fetchInsiderFeed,
  fetchBankrollSummary,
  fetchBetHistory,
} from "@/lib/sportsApi";

import {
  SportsMatchItem,
  ValueBetItem,
  InsiderNewsItem,
  SportsBankrollSummary,
  BetHistoryItem,
} from "@/types/sports";

// --- Trading Terminal Imports ---
import { SystemStatusHeader } from "@/components/SystemStatusHeader";
import { WalletRiskPanel } from "@/components/WalletRiskPanel";
import { ActivePositionsTable } from "@/components/ActivePositionsTable";
import { CandlestickChart } from "@/components/CandlestickChart";
import { InteractiveRunner } from "@/components/InteractiveRunner";
import { AgentReasoningStream } from "@/components/AgentReasoningStream";
import { SystemLogsFeed } from "@/components/SystemLogsFeed";
import { MarketScreenerWidget } from "@/components/MarketScreenerWidget";
import { NewsCatalystFeedWidget } from "@/components/NewsCatalystFeedWidget";
import { useTradingWS, WSMessage } from "@/hooks/useTradingWS";
import {
  fetchSystemStatus,
  fetchWallet,
  fetchPositions,
  fetchKlines,
  fetchLogs,
  fetchFeeRate,
  fetchScreenerSnapshot,
  fetchCatalystFeed,
} from "@/lib/api";
import {
  SystemStatusResponse,
  WalletBalanceResponse,
  ActivePosition,
  CandlestickData,
  TradingDecision,
  TechnicalIndicators,
  TradingSystemLogItem,
  FeeRateInfo,
  ScreenerSnapshot,
  NewsCatalystEvent,
} from "@/types/trading";

export default function MainDashboardPage() {
  // Navigation State: "sports" (Букмекерская Аналитика) or "trading" (Crypto Terminal)
  const [activeTab, setActiveTab] = useState<"sports" | "trading">("sports");

  // --- Sports Betting Analytics State ---
  const [sportsMatches, setSportsMatches] = useState<SportsMatchItem[]>([]);
  const [valueBets, setValueBets] = useState<ValueBetItem[]>([]);
  const [insiderFeed, setInsiderFeed] = useState<InsiderNewsItem[]>([]);
  const [bankrollSummary, setBankrollSummary] = useState<SportsBankrollSummary | null>(null);
  const [betHistory, setBetHistory] = useState<BetHistoryItem[]>([]);
  const [selectedMatchForModal, setSelectedMatchForModal] = useState<string | null>(null);
  const [isLoadingSports, setIsLoadingSports] = useState<boolean>(true);

  // --- Trading Terminal State ---
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [wallet, setWallet] = useState<WalletBalanceResponse | null>(null);
  const [positions, setPositions] = useState<ActivePosition[]>([]);
  const [klines, setKlines] = useState<CandlestickData[]>([]);
  const [logs, setLogs] = useState<TradingSystemLogItem[]>([]);
  const [decision, setDecision] = useState<TradingDecision | null>(null);
  const [techIndicators, setTechIndicators] = useState<TechnicalIndicators | null>(null);
  const [feeRate, setFeeRate] = useState<FeeRateInfo | null>(null);
  const [screener, setScreener] = useState<ScreenerSnapshot | null>(null);
  const [catalystFeed, setCatalystFeed] = useState<NewsCatalystEvent[]>([]);

  const [symbol, setSymbol] = useState<string>("BTCUSDT");
  const [timeframe, setTimeframe] = useState<string>("15");
  const [mode, setMode] = useState<"fast" | "deep">("fast");
  const [isLive, setIsLive] = useState<boolean>(false);
  const [isLoadingChart, setIsLoadingChart] = useState<boolean>(false);

  // Load Sports Analytics Data
  const loadSportsData = useCallback(async () => {
    setIsLoadingSports(true);
    try {
      const [matches, bets, news, bankroll, history] = await Promise.all([
        fetchSportsMatches(),
        fetchValueBets(),
        fetchInsiderFeed(),
        fetchBankrollSummary(),
        fetchBetHistory(),
      ]);
      setSportsMatches(matches);
      setValueBets(bets);
      setInsiderFeed(news);
      setBankrollSummary(bankroll);
      setBetHistory(history);
    } catch (e) {
      console.error("Failed to load sports data:", e);
    } finally {
      setIsLoadingSports(false);
    }
  }, []);

  const handleSyncOddsNow = async () => {
    const res = await syncOdds();
    if (res.matches) {
      setSportsMatches(res.matches);
    }
    await loadSportsData();
  };

  // Load Trading Terminal Data
  const loadKlines = useCallback(async (sym: string, tf: string) => {
    setIsLoadingChart(true);
    try {
      const [data, fee] = await Promise.all([
        fetchKlines(sym, tf, 100),
        fetchFeeRate(sym).catch(() => null),
      ]);
      setKlines(data.klines);
      if (data.technical_indicators) setTechIndicators(data.technical_indicators);
      if (fee) setFeeRate(fee);
    } catch (e) {
      console.error("Failed to load klines or fees:", e);
    } finally {
      setIsLoadingChart(false);
    }
  }, []);

  const refreshTrading = useCallback(async () => {
    try {
      const [s, w, p, l, scr, cat] = await Promise.all([
        fetchSystemStatus().catch(() => null),
        fetchWallet().catch(() => null),
        fetchPositions().catch(() => []),
        fetchLogs(15).catch(() => []),
        fetchScreenerSnapshot().catch(() => null),
        fetchCatalystFeed(20).catch(() => ({ feed: [] })),
      ]);
      if (s) setStatus(s);
      if (w) setWallet(w);
      if (p) setPositions(p);
      if (l) setLogs(l);
      if (scr) setScreener(scr);
      if (cat && cat.feed) setCatalystFeed(cat.feed);
    } catch (e) {
      console.error("Error refreshing trading data:", e);
    }
  }, []);

  useEffect(() => {
    loadSportsData();
    refreshTrading();
    loadKlines(symbol, timeframe);

    const interval = setInterval(() => {
      loadSportsData();
      refreshTrading();
    }, 15000);

    return () => clearInterval(interval);
  }, [loadSportsData, refreshTrading, loadKlines, symbol, timeframe]);

  // WebSocket for Trading Terminal
  const handleWSMessage = useCallback(
    (msg: WSMessage) => {
      if (msg.type === "ANALYSIS_COMPLETED" && msg.decision) {
        setDecision(msg.decision);
      } else if (msg.type === "EXECUTION_RESULT" || msg.type === "EMERGENCY_STOP_ACTIVATED") {
        refreshTrading();
      }
    },
    [refreshTrading]
  );

  const { isConnected: wsConnected } = useTradingWS(handleWSMessage);

  const unrealisedPnlTotal = positions.reduce((acc, p) => acc + (p.unrealised_pnl || 0), 0);

  return (
    <div className="flex flex-col min-h-screen bg-slate-950 text-slate-100 selection:bg-emerald-500 selection:text-slate-950">
      
      {/* 1. Global Navigation Header */}
      <SportsHeader
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onSyncOdds={handleSyncOddsNow}
        bankroll={bankrollSummary?.totalBankroll || 12480}
        roiPercentage={bankrollSummary?.roiPercentage || 18.4}
        activeValueBetsCount={valueBets.length}
      />

      {/* 2. Main Content Container */}
      <main className="max-w-[1700px] mx-auto p-4 flex-1 w-full space-y-5">
        
        {/* ======================================================== */}
        {/* VIEW 1: SPORTS BETTING ANALYTICS DASHBOARD              */}
        {/* ======================================================== */}
        {activeTab === "sports" && (
          <>
            {/* Top Section: EV+ Value Bets Scanner */}
            <ValueBetsScanner
              valueBets={valueBets}
              onSelectMatchForAnalysis={(match_id) => setSelectedMatchForModal(match_id)}
              isLoading={isLoadingSports}
            />

            {/* Middle Section: Odds Comparison Radar & Insider News RAG */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              <div className="lg:col-span-7">
                <OddsComparisonWidget
                  matches={sportsMatches}
                  onSelectMatch={(match_id) => setSelectedMatchForModal(match_id)}
                />
              </div>

              <div className="lg:col-span-5">
                <InsiderFeedWidget
                  feed={insiderFeed}
                  onRefresh={loadSportsData}
                />
              </div>
            </div>

            {/* Bottom Section: Bankroll Tracker & Value Bet History */}
            {bankrollSummary && (
              <BankrollTracker
                summary={bankrollSummary}
                bets={betHistory}
              />
            )}

            {/* Interactive LangGraph AI Analysis Modal */}
            <MatchAnalysisModal
              matchId={selectedMatchForModal}
              onClose={() => setSelectedMatchForModal(null)}
            />
          </>
        )}

        {/* ======================================================== */}
        {/* VIEW 2: CRYPTO TRADING TERMINAL                          */}
        {/* ======================================================== */}
        {activeTab === "trading" && (
          <>
            <SystemStatusHeader status={status} wsConnected={wsConnected} />

            <WalletRiskPanel
              wallet={wallet}
              unrealisedPnl={unrealisedPnlTotal}
              onEmergencyStopTriggered={refreshTrading}
            />

            <NewsCatalystFeedWidget
              feed={catalystFeed}
              activeSymbol={symbol}
              onSelectSymbol={(s) => {
                setSymbol(s);
                loadKlines(s, timeframe);
              }}
              onRefresh={refreshTrading}
            />

            <MarketScreenerWidget
              snapshot={screener}
              activeSymbol={symbol}
              onSelectSymbol={(s) => {
                setSymbol(s);
                loadKlines(s, timeframe);
              }}
              onRefresh={refreshTrading}
            />

            <section className="grid grid-cols-1 lg:grid-cols-12 gap-4">
              <InteractiveRunner
                symbol={symbol}
                timeframe={timeframe}
                mode={mode}
                isLive={isLive}
                feeRate={feeRate}
                onSymbolChange={(s) => {
                  setSymbol(s);
                  loadKlines(s, timeframe);
                }}
                onTimeframeChange={(tf) => {
                  setTimeframe(tf);
                  loadKlines(symbol, tf);
                }}
                onModeChange={setMode}
                onLiveChange={setIsLive}
                onAnalysisDone={(dec, tech) => {
                  setDecision(dec);
                  setTechIndicators(tech);
                  refreshTrading();
                }}
                onExecutionDone={refreshTrading}
              />

              <CandlestickChart
                symbol={symbol}
                klines={klines}
                techIndicators={techIndicators}
                isLoading={isLoadingChart}
              />
            </section>

            <ActivePositionsTable positions={positions} onRefresh={refreshTrading} />

            <section className="grid grid-cols-1 lg:grid-cols-12 gap-4">
              <AgentReasoningStream
                symbol={symbol}
                timeframe={timeframe}
                decision={decision}
              />

              <SystemLogsFeed logs={logs} onRefresh={refreshTrading} />
            </section>
          </>
        )}

      </main>
    </div>
  );
}
