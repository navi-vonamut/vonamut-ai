"use client";

import React, { useEffect, useState } from "react";
import { Radio } from "lucide-react";
import { SystemStatusResponse } from "@/types/trading";

interface Props {
  status: SystemStatusResponse | null;
  wsConnected: boolean;
}

export function SystemStatusHeader({ status, wsConnected }: Props) {
  const [timeStr, setTimeStr] = useState("--:--:-- UTC");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(now.toUTCString().slice(17, 25) + " UTC");
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const circuits = status?.circuits || {};

  return (
    <header className="border-b border-card-border bg-[#0c0c0e]/90 backdrop-blur sticky top-0 z-50 px-4 py-2.5">
      <div className="max-w-[1700px] mx-auto flex flex-wrap items-center justify-between gap-4">
        
        {/* Brand & Mode */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded border border-zinc-700 bg-black flex items-center justify-center font-mono font-bold text-sm tracking-wider text-white">
            VN
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm tracking-tight text-white">VONAMUT TERMINAL</span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">Next.js 16</span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-amber-950/60 border border-amber-800/80 text-amber-300">
                {circuits.bybit?.demo ? "BYBIT DEMO" : "BYBIT LIVE"}
              </span>
            </div>
            <div className="text-[11px] text-zinc-500 font-mono flex items-center gap-2">
              <span>Autonomous Intelligence Unit</span>
              <span>•</span>
              <span>{timeStr}</span>
            </div>
          </div>
        </div>

        {/* 4 Circuit Indicators */}
        <div className="flex items-center flex-wrap gap-2 text-xs font-mono">
          
          {/* Circuit 1: Database */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-zinc-950 border border-zinc-800">
            <span
              className={`w-2 h-2 rounded-full ${
                circuits.database?.status === "online" ? "bg-emerald-500 shadow-[0_0_8px_#22c55e]" : "bg-red-500"
              }`}
            />
            <span className="text-zinc-400 text-[11px]">POSTGRES</span>
            <span className="text-[10px] text-zinc-500">{circuits.database?.latency_ms ?? "--"}ms</span>
          </div>

          {/* Circuit 2: Qdrant */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-zinc-950 border border-zinc-800">
            <span
              className={`w-2 h-2 rounded-full ${
                circuits.qdrant?.status === "online" ? "bg-emerald-500 shadow-[0_0_8px_#22c55e]" : "bg-red-500"
              }`}
            />
            <span className="text-zinc-400 text-[11px]">QDRANT (3072d)</span>
            <span className="text-[10px] text-zinc-500">{circuits.qdrant?.latency_ms ?? "--"}ms</span>
          </div>

          {/* Circuit 3: Bybit */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-zinc-950 border border-zinc-800">
            <span
              className={`w-2 h-2 rounded-full ${
                circuits.bybit?.status === "online" ? "bg-emerald-500 shadow-[0_0_8px_#22c55e]" : "bg-red-500"
              }`}
            />
            <span className="text-zinc-400 text-[11px]">BYBIT V5</span>
            <span className="text-[10px] text-zinc-500">{circuits.bybit?.latency_ms ?? "--"}ms</span>
          </div>

          {/* Circuit 4: Gemini / Gemma AI */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-zinc-950 border border-zinc-800">
            <span
              className={`w-2 h-2 rounded-full ${
                circuits.gemini_ai?.status === "online" ? "bg-emerald-500 shadow-[0_0_8px_#22c55e]" : "bg-amber-500"
              }`}
            />
            <span className="text-zinc-400 text-[11px]">GEMINI & GEMMA</span>
          </div>

          {/* Live WS Status */}
          <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-[11px]">
            <Radio className={`w-3.5 h-3.5 ${wsConnected ? "text-emerald-400" : "text-amber-400 animate-pulse"}`} />
            <span className={wsConnected ? "text-emerald-400 font-semibold" : "text-amber-400 font-semibold"}>
              {wsConnected ? "LIVE WS" : "RECONNECTING"}
            </span>
          </div>

        </div>

      </div>
    </header>
  );
}
