"use client";

import React, { useState } from "react";
import { Flame, RefreshCw, TrendingUp, TrendingDown, DollarSign, Activity, Check } from "lucide-react";
import { ScreenerSnapshot, ScreenerTicker } from "@/types/trading";
import { triggerScreenerScan } from "@/lib/api";

interface Props {
  snapshot: ScreenerSnapshot | null;
  activeSymbol: string;
  onSelectSymbol: (symbol: string) => void;
  onRefresh: () => void;
}

export function MarketScreenerWidget({
  snapshot,
  activeSymbol,
  onSelectSymbol,
  onRefresh,
}: Props) {
  const [isScanning, setIsScanning] = useState(false);

  const handleScanNow = async () => {
    setIsScanning(true);
    try {
      await triggerScreenerScan();
      onRefresh();
    } catch (e) {
      alert(`Screener scan failed: ${e}`);
    } finally {
      setIsScanning(false);
    }
  };

  const tickers = snapshot?.tickers || [];
  const timeStr = snapshot?.timestamp
    ? new Date(snapshot.timestamp * 1000).toLocaleTimeString()
    : "--:--:--";

  return (
    <section className="bg-card border border-card-border rounded-lg p-4">
      
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-card-border">
        <div className="flex items-center gap-2">
          <Flame className="w-4 h-4 text-amber-500 animate-pulse" />
          <span className="font-semibold text-sm text-white">Market Screener (Dynamic Radar)</span>
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
            {tickers.length} Hot Movers
          </span>
          <span className="text-[11px] font-mono text-zinc-500 hidden sm:inline">
            Vol &gt; $20M • 24h &gt; 5% / 1h &gt; 2% • OI Growth
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-zinc-500 hidden md:inline">
            Last scan: {timeStr}
          </span>
          <button
            onClick={handleScanNow}
            disabled={isScanning}
            className="text-xs text-zinc-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 px-2.5 py-1 rounded font-mono flex items-center gap-1.5 transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3 h-3 ${isScanning ? "animate-spin text-amber-400" : ""}`} />
            <span>{isScanning ? "Scanning..." : "Scan Market"}</span>
          </button>
        </div>
      </div>

      {/* Hot Pairs Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2.5 mt-3">
        {tickers.length === 0 ? (
          <div className="col-span-full py-6 text-center text-zinc-500 text-xs font-mono">
            No hot movers matching strict filters ($20M+ Vol, 5%+ Change). Click &quot;Scan Market&quot; to refresh.
          </div>
        ) : (
          tickers.map((t) => {
            const isSelected = activeSymbol === t.symbol;
            const isPos24 = t.price_change_24h_pct >= 0;
            const isPos1h = t.price_change_1h_pct >= 0;

            const biasClass =
              t.direction_bias === "BULLISH"
                ? "bg-emerald-950/80 text-emerald-300 border-emerald-800/80"
                : t.direction_bias === "BEARISH"
                ? "bg-red-950/80 text-red-300 border-red-800/80"
                : "bg-zinc-900 text-zinc-400 border-zinc-800";

            return (
              <div
                key={t.symbol}
                onClick={() => onSelectSymbol(t.symbol)}
                className={`p-3 rounded-lg border cursor-pointer transition flex flex-col justify-between ${
                  isSelected
                    ? "bg-zinc-900/90 border-white shadow-[0_0_12px_rgba(255,255,255,0.15)]"
                    : "bg-zinc-950/70 border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-900/40"
                }`}
              >
                <div>
                  {/* Symbol & Bias */}
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm font-mono text-white flex items-center gap-1.5">
                      {t.symbol}
                      {isSelected && <Check className="w-3.5 h-3.5 text-emerald-400" />}
                    </span>
                    <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded border ${biasClass}`}>
                      {t.direction_bias}
                    </span>
                  </div>

                  {/* Price & Volume */}
                  <div className="flex items-baseline justify-between mt-2 font-mono text-xs">
                    <span className="text-zinc-200 font-semibold">${t.last_price}</span>
                    <span className="text-[11px] text-zinc-500">
                      ${(t.turnover_24h_usd / 1_000_000).toFixed(1)}M Vol
                    </span>
                  </div>

                  {/* 24h & 1h Changes */}
                  <div className="grid grid-cols-2 gap-1.5 mt-2 font-mono text-[11px]">
                    <div className="bg-zinc-900/80 p-1 rounded flex items-center justify-between">
                      <span className="text-zinc-500">24h:</span>
                      <span className={`font-semibold ${isPos24 ? "text-emerald-400" : "text-red-400"}`}>
                        {isPos24 ? "+" : ""}{t.price_change_24h_pct}%
                      </span>
                    </div>
                    <div className="bg-zinc-900/80 p-1 rounded flex items-center justify-between">
                      <span className="text-zinc-500">1h:</span>
                      <span className={`font-semibold ${isPos1h ? "text-emerald-400" : "text-red-400"}`}>
                        {isPos1h ? "+" : ""}{t.price_change_1h_pct}%
                      </span>
                    </div>
                  </div>
                </div>

                {/* Open Interest Growth Badge */}
                <div className="mt-2.5 pt-2 border-t border-zinc-900/80 flex items-center justify-between text-[10px] font-mono">
                  <div className="flex items-center gap-1">
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        t.is_oi_growing ? "bg-emerald-400 shadow-[0_0_6px_#22c55e]" : "bg-zinc-600"
                      }`}
                    />
                    <span className={t.is_oi_growing ? "text-emerald-400 font-semibold" : "text-zinc-500"}>
                      {t.is_oi_growing ? `OI +${t.oi_change_pct}%` : "OI Neutral"}
                    </span>
                  </div>
                  <span className="text-zinc-500">Score: {t.score}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
