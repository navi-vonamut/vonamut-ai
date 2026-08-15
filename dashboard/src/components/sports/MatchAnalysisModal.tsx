"use client";

import React, { useEffect, useState } from "react";
import { MatchAnalysisResult } from "@/types/sports";
import { analyzeMatch } from "@/lib/sportsApi";
import {
  X,
  BrainCircuit,
  Sparkles,
  ShieldAlert,
  CheckCircle,
  TrendingUp,
  FileText,
  Activity,
  Layers,
} from "lucide-react";

interface MatchAnalysisModalProps {
  matchId: string | null;
  onClose: () => void;
}

export function MatchAnalysisModal({ matchId, onClose }: MatchAnalysisModalProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MatchAnalysisResult | null>(null);

  useEffect(() => {
    if (!matchId) return;

    let isMounted = true;
    setLoading(true);
    setResult(null);

    analyzeMatch(matchId)
      .then((res) => {
        if (isMounted) {
          setResult(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error("Match analysis failed:", err);
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [matchId]);

  if (!matchId) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-5 relative max-h-[90vh] overflow-y-auto">
        
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-white rounded-lg bg-slate-800/50 hover:bg-slate-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 text-slate-950 font-bold shadow-lg shadow-emerald-500/20">
            <BrainCircuit className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-extrabold text-white flex items-center gap-2">
              LangGraph Multi-Node Match Deep Dive
              <span className="px-2 py-0.5 text-[10px] rounded bg-emerald-500/20 text-emerald-300 font-semibold border border-emerald-500/30">
                3-Node AI Graph
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Комплексный AI-анализ матча, векторных инсайдов и математического математического математического математического математического перевеса
            </p>
          </div>
        </div>

        {/* Loading State */}
        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center space-y-4">
            <div className="relative">
              <div className="w-12 h-12 rounded-full border-4 border-emerald-500/20 border-t-emerald-500 animate-spin"></div>
              <Sparkles className="w-5 h-5 text-emerald-400 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-white">Выполнение LangGraph Графа...</p>
              <p className="text-xs text-slate-400 mt-1">
                Узел 1: Ингемпинг инсайдов Qdrant ➔ Узел 2: AI Расчет Вероятностей ➔ Узел 3: Фильтрация EV+
              </p>
            </div>
          </div>
        ) : result ? (
          <div className="space-y-4 text-xs">
            
            {/* Match Banner & Value Bet Verdict */}
            <div className="p-4 bg-slate-950/80 rounded-xl border border-slate-800 flex items-center justify-between">
              <div>
                <span className="text-[11px] text-slate-400 block uppercase">Анализируемый Матч</span>
                <span className="text-base font-extrabold text-white">{result.match}</span>
              </div>

              {result.is_value_bet ? (
                <div className="px-3 py-1.5 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-extrabold flex items-center gap-1.5 text-xs">
                  <CheckCircle className="w-4 h-4" />
                  <span>ВАЛУЙ ОБНАРУЖЕН (+{result.value_percentage}%)</span>
                </div>
              ) : (
                <div className="px-3 py-1.5 rounded-xl bg-slate-800 text-slate-400 font-semibold flex items-center gap-1.5 text-xs">
                  <ShieldAlert className="w-4 h-4" />
                  <span>НЕТ ПЕРЕВЕСА</span>
                </div>
              )}
            </div>

            {/* Metrics Breakdown Grid */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800 text-center">
                <span className="text-[10px] text-slate-400 block uppercase">Рекомендация</span>
                <span className="text-sm font-black text-emerald-400 block mt-0.5">
                  {result.best_outcome || "Пропустить"}
                </span>
              </div>
              <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800 text-center">
                <span className="text-[10px] text-slate-400 block uppercase">Кэф Pinnacle</span>
                <span className="text-sm font-black text-amber-400 block mt-0.5">
                  {result.odds ? result.odds.toFixed(2) : "N/A"}
                </span>
              </div>
              <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800 text-center">
                <span className="text-[10px] text-slate-400 block uppercase">AI Вероятность</span>
                <span className="text-sm font-black text-cyan-400 block mt-0.5">
                  {result.ai_probability ? `${(result.ai_probability * 100).toFixed(1)}%` : "N/A"}
                </span>
              </div>
            </div>

            {/* AI Probability vs Implied Odds Bar */}
            <div className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-800 space-y-2">
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-slate-300 font-medium">Сравнение вероятностей:</span>
                <span className="text-emerald-400 font-bold">
                  AI Model {(result.ai_probability ? result.ai_probability * 100 : 0).toFixed(1)}% vs БК {result.odds ? (100 / result.odds).toFixed(1) : 0}%
                </span>
              </div>
              <div className="w-full h-3 bg-slate-900 rounded-full overflow-hidden flex">
                <div
                  className="bg-emerald-500 h-full transition-all duration-500"
                  style={{ width: `${(result.ai_probability || 0.5) * 100}%` }}
                ></div>
                <div
                  className="bg-cyan-600/50 h-full transition-all duration-500"
                  style={{ width: `${100 - (result.ai_probability || 0.5) * 100}%` }}
                ></div>
              </div>
            </div>

            {/* Qdrant Vector Context Section */}
            {result.insider_context_found && result.insider_context_found.length > 0 && (
              <div className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-800 space-y-2">
                <span className="text-[11px] font-bold text-cyan-400 flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5" />
                  Извлеченный Контекст Qdrant Vector Store:
                </span>
                <ul className="space-y-1 list-disc list-inside text-slate-300">
                  {result.insider_context_found.map((ctx, i) => (
                    <li key={i}>{ctx}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* AI Reasoning Text */}
            <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800 space-y-1.5">
              <span className="text-[11px] font-bold text-amber-400 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5" />
                Полный лог работы агента (Reasoning):
              </span>
              <p className="text-slate-200 leading-relaxed font-mono whitespace-pre-wrap text-[11px] bg-slate-900/60 p-3 rounded border border-slate-800/60">
                {result.ai_reasoning}
              </p>
            </div>

            {/* Close Button Footer */}
            <div className="pt-2 flex justify-end">
              <button
                onClick={onClose}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg font-semibold text-xs transition-colors"
              >
                Закрыть
              </button>
            </div>

          </div>
        ) : null}

      </div>
    </div>
  );
}
