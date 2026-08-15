"use client";

import React from "react";
import { List } from "lucide-react";
import { TradingSystemLogItem } from "@/types/trading";

interface Props {
  logs: TradingSystemLogItem[];
  onRefresh: () => void;
}

export function SystemLogsFeed({ logs, onRefresh }: Props) {
  return (
    <div className="lg:col-span-4 bg-card border border-card-border rounded-lg p-4 flex flex-col">
      <div className="flex items-center justify-between pb-3 border-b border-card-border">
        <div className="flex items-center gap-2">
          <List className="w-4 h-4 text-white" />
          <span className="font-semibold text-sm text-white">System & Node Logs</span>
        </div>
        <button
          onClick={onRefresh}
          className="text-xs text-zinc-400 hover:text-white font-mono transition"
        >
          Sync
        </button>
      </div>

      <div className="flex-1 max-h-[300px] overflow-y-auto space-y-2 mt-3 text-[11px] font-mono pr-1">
        {logs.length === 0 ? (
          <div className="text-zinc-600 text-center py-6">Connecting to log stream...</div>
        ) : (
          logs.map((l) => {
            const isSignal = l.level === "SIGNAL_ALERT" || l.level === "ORDER_PLACED";
            const borderClass = isSignal
              ? "border-emerald-800/80 bg-emerald-950/20"
              : "border-zinc-900 bg-zinc-950";
            const timeStr = l.created_at ? l.created_at.slice(11, 19) : "--:--";

            return (
              <div key={l.id || l.created_at} className={`p-2 rounded border ${borderClass}`}>
                <div className="flex items-center justify-between text-zinc-500 text-[10px]">
                  <span>[{l.component}]</span>
                  <span>{timeStr}</span>
                </div>
                <div className="text-zinc-300 mt-1">{l.message_ru || l.message_en}</div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
