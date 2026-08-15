"use client";

import React, { useState } from "react";
import { ValueBetItem } from "@/types/sports";
import {
  Flame,
  Search,
  Sparkles,
  TrendingUp,
  BrainCircuit,
  Percent,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Zap,
} from "lucide-react";

interface ValueBetsScannerProps {
  valueBets: ValueBetItem[];
  onSelectMatchForAnalysis: (match_id: string) => void;
  isLoading: boolean;
}

export function ValueBetsScanner({
  valueBets,
  onSelectMatchForAnalysis,
  isLoading,
}: ValueBetsScannerProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedLeague, setSelectedLeague] = useState<string>("ALL");

  const leagues = [
    "ALL",
    ...Array.from(new Set(valueBets.map((b) => b.league))),
  ];

  const filteredBets = valueBets.filter((bet) => {
    const matchesSearch =
      bet.team1.toLowerCase().includes(searchQuery.toLowerCase()) ||
      bet.team2.toLowerCase().includes(searchQuery.toLowerCase()) ||
      bet.bet_target.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesLeague =
      selectedLeague === "ALL" || bet.league === selectedLeague;
    return matchesSearch && matchesLeague;
  });

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl backdrop-blur-md flex flex-col space-y-4">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-3 border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <Flame className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              Сканер Валуев (EV+ Market Edge)
              <span className="px-2 py-0.5 text-[11px] rounded-full bg-emerald-500/20 text-emerald-300 font-extrabold">
                {filteredBets.length} Валуев Найдено
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Матчи с перевесом относительно коэффициентов Pinnacle & 1xBet
            </p>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2.5 w-full sm:w-auto">
          {/* Search Input */}
          <div className="relative flex-1 sm:w-48">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Поиск команды..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-slate-950/80 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500/50 transition-colors"
            />
          </div>

          {/* League Selector */}
          <div className="flex items-center gap-1 overflow-x-auto max-w-full pb-1 sm:pb-0 scrollbar-none">
            {leagues.map((league) => (
              <button
                key={league}
                onClick={() => setSelectedLeague(league)}
                className={`px-2.5 py-1 text-[11px] font-semibold rounded-lg transition-all whitespace-nowrap ${
                  selectedLeague === league
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                    : "bg-slate-950/60 text-slate-400 border border-slate-800/60 hover:text-slate-200"
                }`}
              >
                {league === "ALL" ? "Все Лиги" : league.split(" (")[0]}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Value Bets Cards / Grid */}
      {isLoading ? (
        <div className="py-12 flex flex-col items-center justify-center text-slate-500 space-y-2">
          <BrainCircuit className="w-8 h-8 animate-spin text-emerald-400" />
          <p className="text-xs">Загрузка сканера валуев...</p>
        </div>
      ) : filteredBets.length === 0 ? (
        <div className="py-12 text-center text-slate-500 text-xs bg-slate-950/40 rounded-xl border border-slate-800/40">
          Валуйных исходов по выбранным фильтрам не найдено
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredBets.map((bet) => (
            <div
              key={bet.id}
              className="bg-slate-950/90 border border-slate-800/90 hover:border-emerald-500/40 rounded-xl p-4 transition-all hover:shadow-lg hover:shadow-emerald-950/40 group flex flex-col justify-between space-y-3"
            >
              {/* Card Header: League & EV Badge */}
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-medium text-slate-400 truncate max-w-[170px]">
                  {bet.league}
                </span>
                <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-extrabold text-xs">
                  <TrendingUp className="w-3.5 h-3.5" />
                  <span>+{bet.value_percentage}% EV</span>
                </div>
              </div>

              {/* Match Teams */}
              <div>
                <div className="text-sm font-bold text-white group-hover:text-emerald-300 transition-colors flex items-center justify-between">
                  <span>{bet.team1}</span>
                  <span className="text-xs font-normal text-slate-500">VS</span>
                  <span>{bet.team2}</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Цель: <strong className="text-emerald-400 font-semibold">{bet.bet_target}</strong>
                </p>
              </div>

              {/* Odds & AI Probability Breakdown */}
              <div className="grid grid-cols-3 gap-2 bg-slate-900/90 rounded-lg p-2.5 border border-slate-800/70 text-center">
                <div>
                  <span className="text-[10px] text-slate-400 uppercase block">Кэф БК</span>
                  <span className="text-sm font-black text-amber-400">
                    {bet.bookmaker_odds.toFixed(2)}
                  </span>
                  <span className="text-[9px] text-slate-400 block">{bet.bookmaker}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 uppercase block">AI Вероятн.</span>
                  <span className="text-sm font-black text-cyan-400">
                    {(bet.ai_probability * 100).toFixed(1)}%
                  </span>
                  <span className="text-[9px] text-slate-400 block">Модель</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 uppercase block">Стейк Келли</span>
                  <span className="text-sm font-black text-emerald-400">
                    {bet.kelly_stake_percent}%
                  </span>
                  <span className="text-[9px] text-slate-400 block">От банка</span>
                </div>
              </div>

              {/* AI Short Rationale snippet */}
              <p className="text-[11px] text-slate-300 line-clamp-2 leading-relaxed bg-slate-900/40 p-2 rounded border border-slate-800/40 italic">
                "{bet.ai_reasoning}"
              </p>

              {/* Card Footer Actions */}
              <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between">
                <span className="text-[10px] text-slate-500 flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                  Уверенность: <strong className="text-slate-300 font-semibold">{bet.confidence}</strong>
                </span>

                <button
                  onClick={() => onSelectMatchForAnalysis(bet.match_id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-semibold transition-all"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                   LangGraph Анализ
                </button>
              </div>

            </div>
          ))}
        </div>
      )}
    </div>
  );
}
