"use client";

import React, { useState } from "react";
import { Terminal, Zap, Brain, Activity, Play, Loader2, Percent } from "lucide-react";
import { runAnalysis, executeTrade } from "@/lib/api";
import { TradingDecision, TechnicalIndicators, FeeRateInfo } from "@/types/trading";

interface Props {
  symbol: string;
  timeframe: string;
  mode: "fast" | "deep";
  isLive: boolean;
  feeRate: FeeRateInfo | null;
  onSymbolChange: (sym: string) => void;
  onTimeframeChange: (tf: string) => void;
  onModeChange: (m: "fast" | "deep") => void;
  onLiveChange: (l: boolean) => void;
  onAnalysisDone: (dec: TradingDecision, tech: TechnicalIndicators) => void;
  onExecutionDone: () => void;
}

export function InteractiveRunner({
  symbol,
  timeframe,
  mode,
  isLive,
  feeRate,
  onSymbolChange,
  onTimeframeChange,
  onModeChange,
  onLiveChange,
  onAnalysisDone,
  onExecutionDone,
}: Props) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);

  const handleAnalyze = async () => {
    setIsAnalyzing(true);
    try {
      const res = await runAnalysis(symbol, timeframe, mode);
      onAnalysisDone(res.decision, res.technical_indicators);
    } catch (e) {
      alert(`Analysis failed: ${e}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleExecute = async () => {
    setIsExecuting(true);
    try {
      const res = await executeTrade(symbol, timeframe, mode, isLive);
      onAnalysisDone(res.decision, res.technical_indicators);
      onExecutionDone();
      alert(`Execution Result: ${res.status}`);
    } catch (e) {
      alert(`Execution failed: ${e}`);
    } finally {
      setIsExecuting(false);
    }
  };

  const symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"];
  const timeframes = [
    { label: "1m", value: "1" },
    { label: "5m", value: "5" },
    { label: "15m", value: "15" },
    { label: "1h", value: "60" },
    { label: "1D", value: "D" },
  ];

  return (
    <div className="lg:col-span-4 bg-card border border-card-border rounded-lg p-4 flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between pb-3 border-b border-card-border">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-white" />
            <span className="font-semibold text-sm text-white">Interactive Runner</span>
          </div>
          <span className="text-[11px] font-mono text-zinc-500">Manual Control</span>
        </div>

        <div className="space-y-3.5 mt-3.5">
          
          {/* Symbol Picker */}
          <div>
            <label className="block text-xs font-mono text-zinc-400 mb-1.5">ASSET / PAIR</label>
            <div className="grid grid-cols-3 gap-1.5">
              {symbols.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => onSymbolChange(s)}
                  className={`py-1.5 px-2 rounded text-xs font-mono text-center transition ${
                    symbol === s
                      ? "border border-white bg-white text-black font-semibold"
                      : "border border-zinc-800 bg-zinc-950 text-zinc-400 hover:text-white"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Timeframe Picker */}
          <div>
            <label className="block text-xs font-mono text-zinc-400 mb-1.5">TIMEFRAME</label>
            <div className="grid grid-cols-5 gap-1 font-mono text-xs">
              {timeframes.map((tf) => (
                <button
                  key={tf.value}
                  type="button"
                  onClick={() => onTimeframeChange(tf.value)}
                  className={`py-1 rounded text-center transition ${
                    timeframe === tf.value
                      ? "border border-white bg-white text-black font-semibold"
                      : "border border-zinc-800 bg-zinc-950 text-zinc-400 hover:text-white"
                  }`}
                >
                  {tf.label}
                </button>
              ))}
            </div>
          </div>

          {/* Intelligence Model Mode */}
          <div>
            <label className="block text-xs font-mono text-zinc-400 mb-1.5">INTELLIGENCE MODEL</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => onModeChange("fast")}
                className={`p-2 rounded text-left transition ${
                  mode === "fast"
                    ? "border border-white bg-white text-black"
                    : "border border-zinc-800 bg-zinc-950 text-zinc-400 hover:text-white"
                }`}
              >
                <div className="flex items-center gap-1.5 text-xs font-semibold">
                  <Zap className="w-3.5 h-3.5" />
                  FAST MODE
                </div>
                <div className="text-[10px] opacity-80 font-mono mt-0.5">gemini-3.5-flash-lite</div>
              </button>

              <button
                type="button"
                onClick={() => onModeChange("deep")}
                className={`p-2 rounded text-left transition ${
                  mode === "deep"
                    ? "border border-white bg-white text-black"
                    : "border border-zinc-800 bg-zinc-950 text-zinc-400 hover:text-white"
                }`}
              >
                <div className="flex items-center gap-1.5 text-xs font-semibold">
                  <Brain className="w-3.5 h-3.5" />
                  DEEP REASON
                </div>
                <div className="text-[10px] opacity-80 font-mono mt-0.5">gemma-4-31b-it</div>
              </button>
            </div>
          </div>

          {/* Dynamic Bybit Fee Rates Card */}
          <div className="p-2.5 rounded bg-zinc-950 border border-zinc-800 text-xs font-mono">
            <div className="flex items-center justify-between text-zinc-400 mb-1.5">
              <span className="flex items-center gap-1.5 text-white">
                <Percent className="w-3.5 h-3.5 text-amber-400" />
                Bybit Account Fee Rates
              </span>
              <span className="text-[10px] text-zinc-500">GET /v5/account/fee-rate</span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center pt-1 border-t border-zinc-900">
              <div className="bg-zinc-900/60 p-1.5 rounded">
                <div className="text-[10px] text-zinc-500">MAKER</div>
                <div className="font-bold text-white mt-0.5">
                  {feeRate ? `${feeRate.maker_fee_pct}%` : "0.02%"}
                </div>
              </div>
              <div className="bg-zinc-900/60 p-1.5 rounded">
                <div className="text-[10px] text-zinc-500">TAKER</div>
                <div className="font-bold text-amber-300 mt-0.5">
                  {feeRate ? `${feeRate.taker_fee_pct}%` : "0.055%"}
                </div>
              </div>
              <div className="bg-zinc-900/60 p-1.5 rounded">
                <div className="text-[10px] text-zinc-500">BREAKEVEN</div>
                <div className="font-bold text-emerald-400 mt-0.5">
                  {feeRate ? `~${feeRate.roundtrip_taker_fee_pct}%` : "~0.11%"}
                </div>
              </div>
            </div>
          </div>

          {/* Live Execution Switch */}
          <div className="flex items-center justify-between p-2.5 rounded bg-zinc-950 border border-zinc-800">
            <div>
              <div className="text-xs font-medium text-white">Execution Target</div>
              <div
                className={`text-[10px] font-mono ${
                  isLive ? "text-amber-400 font-bold" : "text-zinc-500"
                }`}
              >
                {isLive ? "🚨 LIVE TRADING (Real Bybit Orders)" : "Dry-Run Simulation (No Real Orders)"}
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={isLive}
                onChange={(e) => onLiveChange(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-9 h-5 bg-zinc-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-600"></div>
            </label>
          </div>

        </div>
      </div>

      {/* Action Buttons */}
      <div className="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border-card-border">
        <button
          onClick={handleAnalyze}
          disabled={isAnalyzing || isExecuting}
          className="bg-zinc-100 hover:bg-white text-black font-semibold text-xs py-2.5 px-3 rounded flex items-center justify-center gap-1.5 transition disabled:opacity-50"
        >
          {isAnalyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Activity className="w-4 h-4" />}
          <span>{isAnalyzing ? "ANALYZING..." : "ANALYZE"}</span>
        </button>

        <button
          onClick={handleExecute}
          disabled={isAnalyzing || isExecuting}
          className="bg-zinc-900 hover:bg-zinc-800 text-white border border-zinc-700 font-semibold text-xs py-2.5 px-3 rounded flex items-center justify-center gap-1.5 transition disabled:opacity-50"
        >
          {isExecuting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          <span>{isExecuting ? "EXECUTING..." : "EXECUTE TRADE"}</span>
        </button>
      </div>
    </div>
  );
}
