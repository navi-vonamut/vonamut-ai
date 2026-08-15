"use client";

import React, { useEffect, useRef } from "react";
import { CandlestickData, TechnicalIndicators } from "@/types/trading";
import { createChart, IChartApi, ISeriesApi } from "lightweight-charts";

interface Props {
  symbol: string;
  klines: CandlestickData[];
  techIndicators: TechnicalIndicators | null;
  isLoading: boolean;
}

export function CandlestickChart({ symbol, klines, techIndicators, isLoading }: Props) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 320,
      layout: {
        background: { color: "#121215" },
        textColor: "#71717a",
      },
      grid: {
        vertLines: { color: "#1f1f23" },
        horzLines: { color: "#1f1f23" },
      },
      timeScale: {
        borderColor: "#27272a",
        timeVisible: true,
      },
      rightPriceScale: {
        borderColor: "#27272a",
      },
    });

    const series = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (seriesRef.current && chartRef.current && klines.length > 0) {
      // De-duplicate candles by integer timestamp and sort strictly ascending
      const seenTimes = new Set<number>();
      const formatted: { time: any; open: number; high: number; low: number; close: number }[] = [];

      for (const k of klines) {
        let t = 0;
        if (typeof (k as any).open_time_ms === "number" && (k as any).open_time_ms > 0) {
          t = Math.floor((k as any).open_time_ms / 1000);
        } else if (k.open_time) {
          const parsed = new Date(k.open_time).getTime();
          if (!isNaN(parsed) && parsed > 0) {
            t = Math.floor(parsed / 1000);
          }
        }
        if (t > 0 && !seenTimes.has(t)) {
          seenTimes.add(t);
          formatted.push({
            time: t as any,
            open: Number(k.open),
            high: Number(k.high),
            low: Number(k.low),
            close: Number(k.close),
          });
        }
      }

      formatted.sort((a, b) => Number(a.time) - Number(b.time));

      if (formatted.length > 0) {
        seriesRef.current.setData(formatted);
        chartRef.current.timeScale().fitContent();
      }
    }
  }, [klines]);

  const lastCandle = klines[klines.length - 1];
  const ob = techIndicators?.orderbook_imbalance;

  return (
    <div className="lg:col-span-8 bg-card border border-card-border rounded-lg p-4 flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between pb-3 border-b border-card-border">
          <div className="flex items-center gap-3 font-mono">
            <span className="font-bold text-sm text-white">{symbol}</span>
            <span className="text-xs text-zinc-300">
              ${lastCandle ? Number(lastCandle.close).toLocaleString("en-US", { minimumFractionDigits: 2 }) : "--"}
            </span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
              Trend: {techIndicators?.trend || "--"}
            </span>
          </div>

          {/* Orderbook Imbalance Indicator */}
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className="text-zinc-500">OB Imbalance:</span>
            <span className="font-bold text-emerald-400">
              {ob?.imbalance_ratio ? `${ob.imbalance_ratio}x` : "1.0x"}
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
              {ob?.sentiment || "BALANCED"}
            </span>
          </div>
        </div>

        {/* Chart Canvas */}
        <div className="relative w-full h-[320px] mt-2 rounded overflow-hidden" ref={chartContainerRef}>
          {isLoading && (
            <div className="absolute inset-0 bg-black/60 z-10 flex items-center justify-center text-xs font-mono text-zinc-400">
              Loading candles...
            </div>
          )}
        </div>
      </div>

      {/* Technical Indicators Quick Ticker Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2 mt-3 pt-3 border-t border-card-border text-xs font-mono">
        <div className="bg-zinc-950 p-2 rounded border border-zinc-900">
          <div className="text-[10px] text-zinc-500">RSI (14)</div>
          <div className="font-bold mt-0.5 text-white">
            {techIndicators?.rsi ? `${techIndicators.rsi.value} (${techIndicators.rsi.status})` : "--"}
          </div>
        </div>
        <div className="bg-zinc-950 p-2 rounded border border-zinc-900">
          <div className="text-[10px] text-zinc-500">MACD (12,26,9)</div>
          <div className="font-bold mt-0.5 text-white">
            {techIndicators?.macd ? `${techIndicators.macd.histogram}` : "--"}
          </div>
        </div>
        <div className="bg-zinc-950 p-2 rounded border border-zinc-900">
          <div className="text-[10px] text-zinc-500">EMA (9 / 21)</div>
          <div className="font-bold mt-0.5 text-zinc-300">
            {techIndicators?.ema ? `${techIndicators.ema.ema9} / ${techIndicators.ema.ema21}` : "-- / --"}
          </div>
        </div>
        <div className="bg-zinc-950 p-2 rounded border border-zinc-900">
          <div className="text-[10px] text-zinc-500">EMA (50 / 200)</div>
          <div className="font-bold mt-0.5 text-zinc-300">
            {techIndicators?.ema ? `${techIndicators.ema.ema50} / ${techIndicators.ema.ema200}` : "-- / --"}
          </div>
        </div>
        <div className="bg-zinc-950 p-2 rounded border border-zinc-900">
          <div className="text-[10px] text-zinc-500">ATR (14)</div>
          <div className="font-bold mt-0.5 text-zinc-300">{techIndicators?.atr ?? "--"}</div>
        </div>
        <div className="bg-zinc-950 p-2 rounded border border-zinc-900">
          <div className="text-[10px] text-zinc-500">VOL RATIO</div>
          <div className="font-bold mt-0.5 text-zinc-300">
            {techIndicators?.volume_ratio ? `${techIndicators.volume_ratio}x` : "--"}
          </div>
        </div>
      </div>
    </div>
  );
}
