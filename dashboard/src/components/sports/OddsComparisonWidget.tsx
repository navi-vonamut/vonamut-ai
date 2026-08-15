"use client";

import React, { useState } from "react";
import { SportsMatchItem } from "@/types/sports";
import {
  BarChart2,
  TrendingDown,
  TrendingUp,
  ShieldCheck,
  Zap,
  CheckCircle2,
} from "lucide-react";

interface OddsComparisonWidgetProps {
  matches: SportsMatchItem[];
  onSelectMatch: (matchId: string) => void;
}

export function OddsComparisonWidget({ matches, onSelectMatch }: OddsComparisonWidgetProps) {
  const [selectedMatchId, setSelectedMatchId] = useState<string>(
    matches[0]?.match_id || ""
  );

  const activeMatch =
    matches.find((m) => m.match_id === selectedMatchId) || matches[0];

  if (!activeMatch) return null;

  const bestHome = activeMatch.best_odds?.home;
  const bestAway = activeMatch.best_odds?.away;
  const bestDraw = activeMatch.best_odds?.draw;
  const bookmakerOdds = activeMatch.bookmaker_odds || [];

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl backdrop-blur-md flex flex-col space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-3 border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <BarChart2 className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              Радар Коэффициентов и Маржи БК
              <span className="px-2 py-0.5 text-[10px] rounded-full bg-cyan-500/20 text-cyan-300 font-extrabold">
                Pinnacle vs 1xBet vs Bet365
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Сравнение линий букмекеров и расчет букмекерской маржи в реальном времени
            </p>
          </div>
        </div>

        {/* Match Select Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto max-w-full scrollbar-none pb-1 sm:pb-0">
          {matches.map((m) => (
            <button
              key={m.match_id || m.id}
              onClick={() => {
                setSelectedMatchId(m.match_id);
                onSelectMatch(m.match_id);
              }}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all whitespace-nowrap ${
                selectedMatchId === m.match_id
                  ? "bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold shadow"
                  : "bg-slate-950/60 text-slate-400 border border-slate-800 hover:text-white"
              }`}
            >
              {m.team1} vs {m.team2}
            </button>
          ))}
        </div>
      </div>

      {/* Match Overview Header */}
      <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <span className="text-[11px] text-cyan-400 font-bold block">
            {activeMatch.league}
          </span>
          <div className="text-base font-black text-white flex items-center gap-2 mt-0.5">
            <span>{activeMatch.team1}</span>
            <span className="text-slate-500 font-normal text-xs">VS</span>
            <span>{activeMatch.team2}</span>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs">
          {bestHome && (
            <div className="px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300">
              <span className="text-[10px] block text-slate-400 uppercase">Лучший Кэф (П1)</span>
              <strong className="text-sm font-black text-emerald-400">
                {bestHome.value} ({bestHome.bookmaker})
              </strong>
            </div>
          )}
          {bestAway && (
            <div className="px-3 py-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-300">
              <span className="text-[10px] block text-slate-400 uppercase">Лучший Кэф (П2)</span>
              <strong className="text-sm font-black text-cyan-400">
                {bestAway.value} ({bestAway.bookmaker})
              </strong>
            </div>
          )}
        </div>
      </div>

      {/* Bookmaker Odds Matrix Table */}
      <div className="overflow-x-auto border border-slate-800/80 rounded-xl">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="bg-slate-950/90 text-slate-400 border-b border-slate-800 text-[11px] uppercase">
              <th className="py-2.5 px-4 font-semibold">Букмекер</th>
              <th className="py-2.5 px-4 font-semibold text-center">П1 ({activeMatch.team1})</th>
              {bestDraw && (
                <th className="py-2.5 px-4 font-semibold text-center">Ничья (X)</th>
              )}
              <th className="py-2.5 px-4 font-semibold text-center">П2 ({activeMatch.team2})</th>
              <th className="py-2.5 px-4 font-semibold text-center">Маржа БК</th>
              <th className="py-2.5 px-4 font-semibold text-right">Обновлено</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
            {bookmakerOdds.map((b) => {
              const isBestHome = bestHome && b.homeOdds === bestHome.value;
              const isBestAway = bestAway && b.awayOdds === bestAway.value;

              return (
                <tr key={b.bookmaker} className="hover:bg-slate-900/60 transition-colors">
                  <td className="py-3 px-4 font-bold text-white flex items-center gap-2">
                    <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
                    {b.bookmaker}
                  </td>

                  {/* Home Odds */}
                  <td className="py-3 px-4 text-center">
                    <span
                      className={`inline-block px-2.5 py-1 rounded-md font-bold text-xs ${
                        isBestHome
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm"
                          : "text-slate-200"
                      }`}
                    >
                      {b.homeOdds ? b.homeOdds.toFixed(2) : "-"}
                    </span>
                  </td>

                  {/* Draw Odds if soccer */}
                  {bestDraw && (
                    <td className="py-3 px-4 text-center">
                      <span className="inline-block px-2.5 py-1 rounded-md font-semibold text-slate-300">
                        {b.drawOdds ? b.drawOdds.toFixed(2) : "-"}
                      </span>
                    </td>
                  )}

                  {/* Away Odds */}
                  <td className="py-3 px-4 text-center">
                    <span
                      className={`inline-block px-2.5 py-1 rounded-md font-bold text-xs ${
                        isBestAway
                          ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm"
                          : "text-slate-200"
                      }`}
                    >
                      {b.awayOdds ? b.awayOdds.toFixed(2) : "-"}
                    </span>
                  </td>

                  {/* Margin % */}
                  <td className="py-3 px-4 text-center">
                    <span
                      className={`font-semibold text-xs ${
                        (b.marginPercentage || 2.5) < 2.5
                          ? "text-emerald-400"
                          : (b.marginPercentage || 2.5) < 4.0
                          ? "text-amber-400"
                          : "text-rose-400"
                      }`}
                    >
                      {b.marginPercentage ? b.marginPercentage.toFixed(1) : "2.5"}%
                    </span>
                  </td>

                  <td className="py-3 px-4 text-right text-slate-500 text-[11px]">
                    {b.lastUpdated || "Just now"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

    </div>
  );
}
