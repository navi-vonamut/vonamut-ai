"use client";

import React from "react";
import { SportsBankrollSummary, BetHistoryItem } from "@/types/sports";
import {
  Wallet,
  TrendingUp,
  Percent,
  Award,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  BarChart3,
  DollarSign,
} from "lucide-react";

interface BankrollTrackerProps {
  summary: SportsBankrollSummary;
  bets: BetHistoryItem[];
}

export function BankrollTracker({ summary, bets }: BankrollTrackerProps) {
  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl backdrop-blur-md flex flex-col space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
            <Wallet className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              Трекер Банкролла и История Ставок
              <span className="px-2 py-0.5 text-[10px] rounded-full bg-amber-500/20 text-amber-300 font-extrabold">
                Kelly Criterion Management
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Статистика доходности ROI, распределение капитала и журнал исполненных валуев
            </p>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Card 1: Bankroll */}
        <div className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800/80 flex flex-col justify-between">
          <div className="flex justify-between items-center text-slate-400 text-xs">
            <span>Общий Банкролл</span>
            <Wallet className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2">
            <span className="text-xl font-black text-white">
              ${summary.totalBankroll.toLocaleString()}
            </span>
            <span className="text-[10px] text-emerald-400 block mt-0.5">
              В игре: ${summary.activeStakes}
            </span>
          </div>
        </div>

        {/* Card 2: Net Profit */}
        <div className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800/80 flex flex-col justify-between">
          <div className="flex justify-between items-center text-slate-400 text-xs">
            <span>Чистая Прибыль</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2">
            <span className="text-xl font-black text-emerald-400">
              +${summary.totalProfit.toLocaleString()}
            </span>
            <span className="text-[10px] text-slate-400 block mt-0.5">
              С момента старта
            </span>
          </div>
        </div>

        {/* Card 3: ROI % */}
        <div className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800/80 flex flex-col justify-between">
          <div className="flex justify-between items-center text-slate-400 text-xs">
            <span>Доходность (ROI)</span>
            <Percent className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="mt-2">
            <span className="text-xl font-black text-cyan-400">
              +{summary.roiPercentage}%
            </span>
            <span className="text-[10px] text-slate-400 block mt-0.5">
              Yield на ставку
            </span>
          </div>
        </div>

        {/* Card 4: Win Rate */}
        <div className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800/80 flex flex-col justify-between">
          <div className="flex justify-between items-center text-slate-400 text-xs">
            <span>Винрейт (Win Rate)</span>
            <Award className="w-4 h-4 text-purple-400" />
          </div>
          <div className="mt-2">
            <span className="text-xl font-black text-purple-400">
              {summary.winRate}%
            </span>
            <span className="text-[10px] text-slate-400 block mt-0.5">
              {summary.successfulValueBets} из {summary.totalBetsPlaced} выиграно
            </span>
          </div>
        </div>
      </div>

      {/* Bet History Table */}
      <div className="space-y-2">
        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
          История Валуев и Принятых Решений
        </h3>

        <div className="overflow-x-auto border border-slate-800/80 rounded-xl">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-950/90 text-slate-400 border-b border-slate-800 text-[11px] uppercase">
                <th className="py-2.5 px-4 font-semibold">Матч & Лига</th>
                <th className="py-2.5 px-4 font-semibold">Цель Ставки</th>
                <th className="py-2.5 px-4 font-semibold text-center">Кэф БК</th>
                <th className="py-2.5 px-4 font-semibold text-center">Стейк</th>
                <th className="py-2.5 px-4 font-semibold text-center">EV+ Edge</th>
                <th className="py-2.5 px-4 font-semibold text-center">Статус</th>
                <th className="py-2.5 px-4 font-semibold text-right">P&L</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
              {bets.map((bet) => (
                <tr key={bet.id} className="hover:bg-slate-900/60 transition-colors">
                  <td className="py-3 px-4">
                    <span className="font-bold text-white block">{bet.match}</span>
                    <span className="text-[10px] text-slate-500 block">{bet.league}</span>
                  </td>

                  <td className="py-3 px-4 font-semibold text-emerald-400">
                    {bet.bet_target}
                  </td>

                  <td className="py-3 px-4 text-center font-bold text-amber-400">
                    {bet.odds.toFixed(2)}
                  </td>

                  <td className="py-3 px-4 text-center text-slate-300 font-medium">
                    ${bet.stake}
                  </td>

                  <td className="py-3 px-4 text-center text-emerald-400 font-bold">
                    +{bet.value_percentage}%
                  </td>

                  <td className="py-3 px-4 text-center">
                    {bet.status === "WON" ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-bold text-[10px]">
                        <CheckCircle2 className="w-3 h-3" /> ВЫИГРЫШ
                      </span>
                    ) : bet.status === "LOST" ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 font-bold text-[10px]">
                        <XCircle className="w-3 h-3" /> ПРОИГРЫШ
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-bold text-[10px]">
                        <Clock className="w-3 h-3" /> В ИГРЕ
                      </span>
                    )}
                  </td>

                  <td className="py-3 px-4 text-right font-extrabold text-xs">
                    {bet.profit_loss && bet.profit_loss > 0 ? (
                      <span className="text-emerald-400">+${bet.profit_loss}</span>
                    ) : bet.profit_loss && bet.profit_loss < 0 ? (
                      <span className="text-rose-400">-${Math.abs(bet.profit_loss)}</span>
                    ) : (
                      <span className="text-slate-400">$0</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
