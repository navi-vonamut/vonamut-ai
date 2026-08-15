"use client";

import React from "react";
import { Layers, RefreshCw } from "lucide-react";
import { ActivePosition } from "@/types/trading";
import { closePosition } from "@/lib/api";

interface Props {
  positions: ActivePosition[];
  onRefresh: () => void;
}

export function ActivePositionsTable({ positions, onRefresh }: Props) {
  const handleClose = async (symbol: string) => {
    if (!confirm(`Are you sure you want to market close position for ${symbol}?`)) return;
    try {
      await closePosition(symbol);
      onRefresh();
    } catch (e) {
      alert(`Failed to close position: ${e}`);
    }
  };

  return (
    <section className="bg-card border border-card-border rounded-lg p-4">
      <div className="flex items-center justify-between pb-3 border-b border-card-border">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-white" />
          <span className="font-semibold text-sm text-white">Active Positions</span>
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
            {positions.length} Open
          </span>
        </div>
        <button
          onClick={onRefresh}
          className="text-xs text-zinc-400 hover:text-white font-mono flex items-center gap-1 transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      <div className="overflow-x-auto mt-2">
        <table className="w-full text-left text-xs font-mono">
          <thead className="text-zinc-500 border-b border-zinc-800/80">
            <tr>
              <th className="py-2.5 px-3">ASSET</th>
              <th className="py-2.5 px-3">SIDE</th>
              <th className="py-2.5 px-3">SIZE</th>
              <th className="py-2.5 px-3">ENTRY PRICE</th>
              <th className="py-2.5 px-3">MARK PRICE</th>
              <th className="py-2.5 px-3">UNREALISED PNL</th>
              <th className="py-2.5 px-3">TP / SL</th>
              <th className="py-2.5 px-3 text-right">ACTION</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {positions.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-zinc-500">
                  No active positions open on Bybit Unified account.
                </td>
              </tr>
            ) : (
              positions.map((p) => {
                const isLong = p.side.toLowerCase() === "buy";
                const pnlPositive = p.unrealised_pnl >= 0;

                return (
                  <tr key={p.symbol} className="hover:bg-zinc-900/40 transition">
                    <td className="py-3 px-3 font-bold text-white">{p.symbol}</td>
                    <td className="py-3 px-3">
                      {isLong ? (
                        <span className="px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800/80">
                          LONG {p.leverage}x
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded bg-red-950/80 text-red-300 border border-red-800/80">
                          SHORT {p.leverage}x
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-zinc-300">{p.size}</td>
                    <td className="py-3 px-3 text-zinc-400">${p.entry_price.toFixed(2)}</td>
                    <td className="py-3 px-3 text-zinc-300">${p.mark_price.toFixed(2)}</td>
                    <td className={`py-3 px-3 font-bold ${pnlPositive ? "text-emerald-400" : "text-red-400"}`}>
                      {pnlPositive ? "+" : ""}${p.unrealised_pnl.toFixed(2)}
                    </td>
                    <td className="py-3 px-3 text-[11px] text-zinc-500">
                      TP: {p.take_profit || "--"} / SL: {p.stop_loss || "--"}
                    </td>
                    <td className="py-3 px-3 text-right">
                      <button
                        onClick={() => handleClose(p.symbol)}
                        className="px-2.5 py-1 rounded bg-zinc-800 hover:bg-red-900/80 text-zinc-300 hover:text-white border border-zinc-700 hover:border-red-600 transition text-[11px]"
                      >
                        Close
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
