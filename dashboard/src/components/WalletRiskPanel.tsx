"use client";

import React, { useState } from "react";
import { Wallet, Shield, TrendingUp, PieChart, AlertTriangle, Octagon } from "lucide-react";
import { WalletBalanceResponse } from "@/types/trading";
import { triggerEmergencyStop } from "@/lib/api";

interface Props {
  wallet: WalletBalanceResponse | null;
  unrealisedPnl: number;
  onEmergencyStopTriggered: () => void;
}

export function WalletRiskPanel({ wallet, unrealisedPnl, onEmergencyStopTriggered }: Props) {
  const [isStopping, setIsStopping] = useState(false);

  const equity = wallet?.total_equity || 0;
  const avail = wallet?.available_margin || 0;
  const marginRatio = equity > 0 ? Math.min(100, Math.max(0, ((equity - avail) / equity) * 100)) : 0;

  const handleStop = async () => {
    if (!confirm("🚨 ARE YOU SURE YOU WANT TO TRIGGER EMERGENCY STOP?\nThis will immediately market close all open positions and cancel active orders!")) {
      return;
    }
    setIsStopping(true);
    try {
      const res = await triggerEmergencyStop();
      alert(`🚨 Emergency Stop Completed! Closed ${res.closed_positions_count} positions.`);
      onEmergencyStopTriggered();
    } catch (e) {
      alert(`Emergency stop failed: ${e}`);
    } finally {
      setIsStopping(false);
    }
  };

  return (
    <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
      
      {/* Total Equity */}
      <div className="bg-[#121215] border border-card-border rounded-lg p-3.5 flex flex-col justify-between">
        <div className="flex items-center justify-between text-zinc-400 text-xs font-mono">
          <span>TOTAL EQUITY</span>
          <Wallet className="w-4 h-4 text-zinc-500" />
        </div>
        <div className="mt-2">
          <div className="text-2xl font-bold font-mono tracking-tight text-white">
            ${equity.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-[11px] text-zinc-500 font-mono mt-0.5">Bybit Unified Account</div>
        </div>
      </div>

      {/* Available Margin */}
      <div className="bg-[#121215] border border-card-border rounded-lg p-3.5 flex flex-col justify-between">
        <div className="flex items-center justify-between text-zinc-400 text-xs font-mono">
          <span>AVAILABLE MARGIN</span>
          <Shield className="w-4 h-4 text-zinc-500" />
        </div>
        <div className="mt-2">
          <div className="text-2xl font-bold font-mono tracking-tight text-white">
            ${avail.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-[11px] text-zinc-500 font-mono mt-0.5">Free for new positions</div>
        </div>
      </div>

      {/* Unrealised PnL */}
      <div className="bg-[#121215] border border-card-border rounded-lg p-3.5 flex flex-col justify-between">
        <div className="flex items-center justify-between text-zinc-400 text-xs font-mono">
          <span>UNREALISED PNL</span>
          <TrendingUp className="w-4 h-4 text-zinc-500" />
        </div>
        <div className="mt-2">
          <div className={`text-2xl font-bold font-mono tracking-tight ${unrealisedPnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {unrealisedPnl >= 0 ? "+" : ""}${unrealisedPnl.toFixed(2)}
          </div>
          <div className="text-[11px] text-zinc-500 font-mono mt-0.5">
            {equity > 0 ? ((unrealisedPnl / equity) * 100).toFixed(2) : "0.00"}% Account PnL
          </div>
        </div>
      </div>

      {/* Margin Usage */}
      <div className="bg-[#121215] border border-card-border rounded-lg p-3.5 flex flex-col justify-between">
        <div className="flex items-center justify-between text-zinc-400 text-xs font-mono">
          <span>MARGIN USAGE</span>
          <PieChart className="w-4 h-4 text-zinc-500" />
        </div>
        <div className="mt-2">
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-white">{marginRatio.toFixed(1)}%</span>
            <span className="text-[11px] text-zinc-500 font-mono">Max: 25%</span>
          </div>
          <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden mt-1.5">
            <div
              className={`h-full transition-all duration-300 ${
                marginRatio > 50 ? "bg-red-500" : marginRatio > 25 ? "bg-amber-500" : "bg-emerald-500"
              }`}
              style={{ width: `${marginRatio}%` }}
            />
          </div>
        </div>
      </div>

      {/* Emergency Stop */}
      <div className="bg-[#181111] border border-red-900/60 rounded-lg p-3.5 flex flex-col justify-between">
        <div className="flex items-center justify-between text-red-400 text-xs font-mono">
          <span>RISK KILL-SWITCH</span>
          <AlertTriangle className="w-4 h-4 text-red-500 animate-pulse" />
        </div>
        <div className="mt-2">
          <button
            onClick={handleStop}
            disabled={isStopping}
            className="w-full bg-red-600 hover:bg-red-500 active:bg-red-700 disabled:opacity-50 text-white font-mono font-semibold py-2 px-3 rounded text-xs transition flex items-center justify-center gap-2 shadow-lg shadow-red-950/50"
          >
            <Octagon className="w-4 h-4" />
            {isStopping ? "CLOSING ALL..." : "EMERGENCY STOP"}
          </button>
          <div className="text-[10px] text-red-400/80 font-mono text-center mt-1">Cancel all & close positions</div>
        </div>
      </div>

    </section>
  );
}
