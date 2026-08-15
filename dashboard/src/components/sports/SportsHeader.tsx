"use client";

import React, { useState } from "react";
import {
  Trophy,
  RefreshCw,
  TrendingUp,
  Database,
  ShieldCheck,
  Zap,
  Activity,
  BarChart3,
  LineChart,
} from "lucide-react";

interface SportsHeaderProps {
  activeTab: "sports" | "trading";
  onTabChange: (tab: "sports" | "trading") => void;
  onSyncOdds: () => Promise<void>;
  bankroll: number;
  roiPercentage: number;
  activeValueBetsCount: number;
}

export function SportsHeader({
  activeTab,
  onTabChange,
  onSyncOdds,
  bankroll,
  roiPercentage,
  activeValueBetsCount,
}: SportsHeaderProps) {
  const [isSyncing, setIsSyncing] = useState(false);

  const handleSyncClick = async () => {
    setIsSyncing(true);
    try {
      await onSyncOdds();
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <header className="bg-slate-950/85 backdrop-blur-md border-b border-slate-800/80 sticky top-0 z-40 px-4 py-3 shadow-xl">
      <div className="max-w-[1700px] mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        
        {/* Brand & Terminal Navigation Toggle */}
        <div className="flex items-center gap-4 w-full md:w-auto justify-between md:justify-start">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 via-teal-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                <Trophy className="w-5 h-5 text-slate-950 font-bold" />
              </div>
              <span className="absolute -top-1 -right-1 flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </span>
            </div>

            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-black tracking-tight text-white flex items-center gap-2">
                  VONAMUT <span className="bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">SPORTS ANALYTICS</span>
                </h1>
                <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 uppercase tracking-widest">
                  AI Edge Engine
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Mathematical Value Betting & LangGraph Multi-Agent Betting Intelligence
              </p>
            </div>
          </div>

          {/* Nav Mode Switcher */}
          <div className="hidden sm:flex items-center p-1 bg-slate-900/90 border border-slate-800 rounded-lg">
            <button
              onClick={() => onTabChange("sports")}
              className={`flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                activeTab === "sports"
                  ? "bg-gradient-to-r from-emerald-500 to-teal-600 text-slate-950 shadow-md font-bold"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/50"
              }`}
            >
              <Trophy className="w-3.5 h-3.5" />
              ⚽ Букмекерский Аналитик
            </button>
            <button
              onClick={() => onTabChange("trading")}
              className={`flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                activeTab === "trading"
                  ? "bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-md font-bold"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/50"
              }`}
            >
              <LineChart className="w-3.5 h-3.5" />
              📈 Trading Terminal
            </button>
          </div>
        </div>

        {/* Center/Right Status Badges & Action */}
        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto justify-end">
          
          {/* Quick Bankroll Metric Pill */}
          <div className="hidden lg:flex items-center gap-4 px-3.5 py-1.5 bg-slate-900/80 border border-slate-800 rounded-xl text-xs">
            <div className="flex items-center gap-1.5">
              <span className="text-slate-400">Банкролл:</span>
              <span className="font-bold text-white">${bankroll.toLocaleString()}</span>
            </div>
            <div className="h-3 w-[1px] bg-slate-800"></div>
            <div className="flex items-center gap-1.5">
              <span className="text-slate-400">ROI:</span>
              <span className="font-bold text-emerald-400 flex items-center gap-0.5">
                <TrendingUp className="w-3 h-3" />
                +{roiPercentage}%
              </span>
            </div>
            <div className="h-3 w-[1px] bg-slate-800"></div>
            <div className="flex items-center gap-1.5">
              <span className="text-slate-400">EV+ Сигналы:</span>
              <span className="px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 font-bold text-[11px]">
                {activeValueBetsCount} Активно
              </span>
            </div>
          </div>

          {/* System Services Badges */}
          <div className="flex items-center gap-2 text-[11px]">
            <div className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-900/90 border border-slate-800 text-slate-300">
              <Activity className="w-3 h-3 text-emerald-400" />
              <span>FastAPI</span>
            </div>
            <div className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-900/90 border border-slate-800 text-slate-300">
              <Database className="w-3 h-3 text-cyan-400" />
              <span>Qdrant RAG</span>
            </div>
            <div className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-900/90 border border-slate-800 text-slate-300">
              <ShieldCheck className="w-3 h-3 text-purple-400" />
              <span>Pinnacle Sync</span>
            </div>
          </div>

          {/* Odds Sync Button */}
          <button
            onClick={handleSyncClick}
            disabled={isSyncing}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-slate-950 font-bold text-xs shadow-lg shadow-emerald-500/20 active:scale-95 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? "animate-spin" : ""}`} />
            {isSyncing ? "Синхронизация..." : "Обновить Коэффициенты"}
          </button>
        </div>

      </div>
    </header>
  );
}
