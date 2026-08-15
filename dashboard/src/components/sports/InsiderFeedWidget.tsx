"use client";

import React, { useState } from "react";
import { InsiderNewsItem } from "@/types/sports";
import { ingestInsiderNews } from "@/lib/sportsApi";
import {
  Radio,
  Send,
  Database,
  ShieldAlert,
  CheckCircle,
  MessageSquare,
  Sparkles,
  Zap,
} from "lucide-react";

interface InsiderFeedWidgetProps {
  feed: InsiderNewsItem[];
  onRefresh: () => void;
}

export function InsiderFeedWidget({ feed, onRefresh }: InsiderFeedWidgetProps) {
  const [newsText, setNewsText] = useState("");
  const [source, setSource] = useState("@sports_insider");
  const [team1, setTeam1] = useState("");
  const [team2, setTeam2] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showIngestForm, setShowIngestForm] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newsText.trim() || !team1.trim() || !team2.trim()) return;

    setIsSubmitting(true);
    try {
      await ingestInsiderNews({ text: newsText, source, team1, team2 });
      setNewsText("");
      setTeam1("");
      setTeam2("");
      setShowIngestForm(false);
      onRefresh();
    } catch (err) {
      console.error("Failed to ingest insider:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl backdrop-blur-md flex flex-col space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-400">
            <Radio className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              Инсайд-Лента и RAG Контекст (Qdrant)
              <span className="px-2 py-0.5 text-[10px] rounded-full bg-purple-500/20 text-purple-300 font-extrabold">
                Telegram Firehose
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Сбор новостей, составов и травм из Telegram-каналов в векторное хранилище Qdrant
            </p>
          </div>
        </div>

        <button
          onClick={() => setShowIngestForm(!showIngestForm)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 border border-purple-500/40 text-xs font-semibold transition-all"
        >
          <Sparkles className="w-3.5 h-3.5" />
          {showIngestForm ? "Скрыть Форму" : "+ Добавить Инсайд"}
        </button>
      </div>

      {/* Manual Ingestion Form */}
      {showIngestForm && (
        <form
          onSubmit={handleSubmit}
          className="bg-slate-950/90 border border-purple-500/30 p-4 rounded-xl space-y-3"
        >
          <span className="text-xs font-bold text-purple-300 block">
            Индексация инсайда в векторную базу Qdrant (`sports_context_24h`):
          </span>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <input
              type="text"
              placeholder="Команда 1 (напр. Real Madrid)"
              value={team1}
              onChange={(e) => setTeam1(e.target.value)}
              required
              className="px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50"
            />
            <input
              type="text"
              placeholder="Команда 2 (напр. Barcelona)"
              value={team2}
              onChange={(e) => setTeam2(e.target.value)}
              required
              className="px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50"
            />
            <input
              type="text"
              placeholder="Источник (напр. @sports_insider)"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50"
            />
          </div>

          <textarea
            placeholder="Текст новости / инсайда о матче..."
            value={newsText}
            onChange={(e) => setNewsText(e.target.value)}
            required
            rows={2}
            className="w-full px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50"
          />

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-xs shadow-md transition-all disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              {isSubmitting ? "Отправка в Qdrant..." : "Индексировать Инсайд"}
            </button>
          </div>
        </form>
      )}

      {/* Insider News Items List */}
      <div className="space-y-2.5 max-h-[300px] overflow-y-auto pr-1">
        {feed.map((item) => (
          <div
            key={item.id}
            className="p-3 bg-slate-950/80 border border-slate-800 hover:border-purple-500/40 rounded-xl transition-all space-y-1.5"
          >
            <div className="flex items-center justify-between text-[11px]">
              <div className="flex items-center gap-2">
                <span className="font-bold text-purple-400">{item.source}</span>
                <span className="text-slate-500">•</span>
                <span className="text-slate-300 font-semibold">
                  {item.team1} vs {item.team2}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                  <Database className="w-3 h-3" />
                  Vector Stored
                </span>
                <span className="text-slate-500 text-[10px]">{item.timestamp}</span>
              </div>
            </div>

            <p className="text-xs text-slate-200 leading-relaxed font-normal">
              {item.text}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
