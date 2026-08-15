"use client";

import React, { useState } from "react";
import { Zap, Radio, RefreshCw, AlertTriangle, ArrowUpRight, CheckCircle2, XCircle, ShieldAlert } from "lucide-react";
import { NewsCatalystEvent } from "@/types/trading";
import { pollNewsFirehose } from "@/lib/api";

interface Props {
  feed: NewsCatalystEvent[];
  activeSymbol: string;
  onSelectSymbol: (symbol: string) => void;
  onRefresh: () => void;
}

export function NewsCatalystFeedWidget({
  feed,
  activeSymbol,
  onSelectSymbol,
  onRefresh,
}: Props) {
  const [isPolling, setIsPolling] = useState(false);

  const handlePollNow = async () => {
    setIsPolling(true);
    try {
      const res = await pollNewsFirehose();
      onRefresh();
    } catch (e) {
      alert(`Firehose poll failed: ${e}`);
    } finally {
      setIsPolling(false);
    }
  };

  const getImpactBadge = (score: number) => {
    if (score >= 8) return "bg-red-500/20 text-red-400 border-red-500/40 font-bold";
    if (score >= 6) return "bg-amber-500/20 text-amber-300 border-amber-500/40 font-semibold";
    return "bg-zinc-800 text-zinc-400 border-zinc-700";
  };

  const getEventTypeBadge = (type: string) => {
    switch (type) {
      case "LISTING":
        return "bg-blue-950 text-blue-300 border-blue-800";
      case "EXPLOIT":
        return "bg-red-950 text-red-300 border-red-800 animate-pulse";
      case "PARTNERSHIP":
        return "bg-purple-950 text-purple-300 border-purple-800";
      case "TOKENOMICS":
        return "bg-amber-950 text-amber-300 border-amber-800";
      case "REGULATORY":
        return "bg-orange-950 text-orange-300 border-orange-800";
      default:
        return "bg-zinc-900 text-zinc-500 border-zinc-800";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "EXECUTED":
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />;
      case "ANALYZED":
        return <ArrowUpRight className="w-3.5 h-3.5 text-blue-400" />;
      case "PENDING_ANALYSIS":
        return <ArrowUpRight className="w-3.5 h-3.5 text-amber-400 animate-pulse" />;
      case "MONITORED":
        return <Radio className="w-3.5 h-3.5 text-emerald-500/80" />;
      case "REJECTED_RISK":
        return <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />;
      case "UNLISTED":
        return <XCircle className="w-3.5 h-3.5 text-zinc-600" />;
      default:
        return <XCircle className="w-3.5 h-3.5 text-zinc-600" />;
    }
  };

  return (
    <section className="bg-card border border-card-border rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-card-border">
        <div className="flex items-center gap-2">
          <Radio className="w-4 h-4 text-emerald-400 animate-pulse" />
          <span className="font-semibold text-sm text-white">News-First Catalyst Radar</span>
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
            LLM Fast Triage
          </span>
          <span className="text-[11px] font-mono text-zinc-500 hidden md:inline">
            15s Firehose • Flash-Lite Evaluation • Bybit Linear Auto-Trigger
          </span>
        </div>

        <button
          onClick={handlePollNow}
          disabled={isPolling}
          className="text-xs text-zinc-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 px-2.5 py-1 rounded font-mono flex items-center gap-1.5 transition disabled:opacity-50"
        >
          <RefreshCw className={`w-3 h-3 ${isPolling ? "animate-spin text-amber-400" : ""}`} />
          <span>{isPolling ? "Polling..." : "Poll Firehose"}</span>
        </button>
      </div>

      {/* Catalyst Feed List */}
      <div className="space-y-2 mt-3 max-h-[320px] overflow-y-auto pr-1">
        {feed.length === 0 ? (
          <div className="py-8 text-center text-zinc-500 text-xs font-mono">
            Listening for breaking news catalysts... Click &quot;Poll Firehose&quot; to fetch latest.
          </div>
        ) : (
          feed.map((ev) => {
            const sym = ev.bybit_symbol || ev.triage.symbol;
            const isSelected = activeSymbol === sym;

            return (
              <div
                key={ev.id}
                onClick={() => sym && onSelectSymbol(sym)}
                className={`p-3 rounded-lg border transition cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-3 ${
                  isSelected
                    ? "bg-zinc-900 border-white shadow-[0_0_10px_rgba(255,255,255,0.1)]"
                    : "bg-zinc-950/70 border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-900/40"
                }`}
              >
                {/* Left: Badges & Title */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    {/* Impact Score */}
                    <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${getImpactBadge(ev.triage.impact_score)}`}>
                      Impact {ev.triage.impact_score}/10
                    </span>

                    {/* Event Type */}
                    <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${getEventTypeBadge(ev.triage.event_type)}`}>
                      {ev.triage.event_type}
                    </span>

                    {/* Sentiment */}
                    <span
                      className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                        ev.triage.sentiment === "BULLISH"
                          ? "bg-emerald-950/80 text-emerald-300 border-emerald-800"
                          : ev.triage.sentiment === "BEARISH"
                          ? "bg-red-950/80 text-red-300 border-red-800"
                          : "bg-zinc-900 text-zinc-400 border-zinc-800"
                      }`}
                    >
                      {ev.triage.sentiment}
                    </span>

                    {/* Symbol */}
                    {sym && (
                      <span className="font-mono text-xs font-bold text-white bg-zinc-900 px-2 py-0.5 rounded border border-zinc-700">
                        {sym}
                      </span>
                    )}

                    {/* Source & Time */}
                    <span className="text-[10px] font-mono text-zinc-500">
                      {ev.news.source} • {new Date(ev.created_at * 1000).toLocaleTimeString()}
                    </span>
                  </div>

                  {/* Title */}
                  <div className="text-xs font-medium text-zinc-200 truncate">{ev.news.title}</div>

                  {/* Summary */}
                  <div className="text-[11px] text-zinc-400 mt-0.5 line-clamp-1">
                    {ev.triage.summary_ru || ev.triage.summary_en}
                  </div>
                </div>

                {/* Right: Bybit & Execution Status */}
                <div className="flex items-center gap-3 shrink-0">
                  <div className="text-right font-mono text-xs">
                    <div className="flex items-center gap-1 justify-end text-[11px]">
                      {getStatusIcon(ev.status)}
                      <span className="text-zinc-300 font-semibold">{ev.status}</span>
                    </div>
                    <div
                      className={`text-[10px] ${
                        ev.is_available_on_bybit
                          ? "text-emerald-400 font-medium"
                          : "text-zinc-500"
                      }`}
                    >
                      {ev.is_available_on_bybit ? "Bybit Linear ✓" : "No Bybit Perp"}
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
