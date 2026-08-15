"use client";

import React, { useState } from "react";
import { Cpu, ShieldAlert, CheckCircle2 } from "lucide-react";
import { TradingDecision } from "@/types/trading";

interface Props {
  symbol: string;
  timeframe: string;
  decision: TradingDecision | null;
}

export function AgentReasoningStream({ symbol, timeframe, decision }: Props) {
  const [lang, setLang] = useState<"ru" | "en">("ru");

  const act = decision?.action || "HOLD";
  const conf = Math.round((decision?.confidence || 0) * 100);

  const getActionBadgeClass = () => {
    if (act === "BUY") return "bg-emerald-600 text-white font-bold";
    if (act === "SELL") return "bg-red-600 text-white font-bold";
    return "bg-zinc-800 text-zinc-300 font-bold";
  };

  const reasoningText =
    lang === "ru"
      ? decision?.reasoning_ru || decision?.reasoning_en
      : decision?.reasoning_en;

  const riskNotesText =
    lang === "ru"
      ? decision?.risk_notes_ru || decision?.risk_notes_en
      : decision?.risk_notes_en;

  return (
    <div className="lg:col-span-8 bg-card border border-card-border rounded-lg p-4 flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between pb-3 border-b border-card-border">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-emerald-400" />
            <span className="font-semibold text-sm text-white">Agent Reasoning Stream (LangGraph)</span>
          </div>

          {/* Bilingual Switch */}
          <div className="flex items-center gap-1 bg-zinc-950 border border-zinc-800 p-0.5 rounded text-[11px] font-mono">
            <button
              onClick={() => setLang("ru")}
              className={`px-2 py-0.5 rounded transition ${
                lang === "ru" ? "bg-zinc-800 text-white font-semibold" : "text-zinc-400 hover:text-white"
              }`}
            >
              RU
            </button>
            <button
              onClick={() => setLang("en")}
              className={`px-2 py-0.5 rounded transition ${
                lang === "en" ? "bg-zinc-800 text-white font-semibold" : "text-zinc-400 hover:text-white"
              }`}
            >
              EN (Base)
            </button>
          </div>
        </div>

        {/* Latest Decision Card */}
        <div className="mt-3">
          <div className="p-4 rounded-lg bg-zinc-950 border border-zinc-800 text-xs font-mono space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`px-2.5 py-1 rounded text-sm ${getActionBadgeClass()}`}>
                  {act}
                </span>
                <span className="text-zinc-400">
                  {symbol} ({timeframe}m)
                </span>
                <span className="text-zinc-500">Confidence: {conf}%</span>
              </div>
              <div className="text-[11px] text-zinc-500">
                {decision ? "LIVE DECISION" : "Awaiting execution"}
              </div>
            </div>

            {/* Target Levels */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-zinc-900">
              <div>
                <span className="text-zinc-500 text-[10px]">ENTRY</span>
                <div className="font-bold text-white">
                  {decision?.entry_price ? `$${decision.entry_price}` : "--"}
                </div>
              </div>
              <div>
                <span className="text-zinc-500 text-[10px]">STOP-LOSS</span>
                <div className="font-bold text-red-400">
                  {decision?.stop_loss ? `$${decision.stop_loss}` : "--"}
                </div>
              </div>
              <div>
                <span className="text-zinc-500 text-[10px]">TAKE-PROFIT 1</span>
                <div className="font-bold text-emerald-400">
                  {decision?.take_profit_1 ? `$${decision.take_profit_1}` : "--"}
                </div>
              </div>
              <div>
                <span className="text-zinc-500 text-[10px]">RISK/REWARD</span>
                <div className="font-bold text-zinc-300">
                  {decision?.risk_reward_ratio ? `${decision.risk_reward_ratio}:1` : "--"}
                </div>
              </div>
            </div>

            {/* Reasoning Box */}
            <div className="p-3 rounded bg-zinc-900/60 border border-zinc-800/80 font-sans text-xs text-zinc-300 leading-relaxed">
              {reasoningText ||
                "Ready for analysis. Click 'ANALYZE' or 'EXECUTE TRADE' in the interactive runner."}
            </div>

            {/* Risk Notes Box */}
            <div className="text-[11px] font-mono text-zinc-400 flex items-start gap-2 bg-zinc-900/30 p-2 rounded border border-zinc-900">
              <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <span>{riskNotesText || "Risk factors and invalidation criteria will appear here."}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
