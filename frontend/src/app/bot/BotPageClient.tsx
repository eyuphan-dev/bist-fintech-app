"use client";

import React from "react";
import { Bot } from "lucide-react";
import PersonalBotPanel from "../components/PersonalBotPanel";
import { useAuth } from "../context/AuthContext";

export default function BotPageClient() {
  const { token } = useAuth();

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-10">
      <div>
        <h1 className="text-xl font-bold text-white">Kişisel AI Trader (Quant Bot)</h1>
        <p className="text-xs text-gray-500 mt-1">
          BİST seans saatlerinde (10:00-18:15) yalnızca sizin için otonom çalışan, süre/zaman
          dilimi bazlı stratejilerle RSI/MACD/Trend analizleri yapan kişisel sanal işlem botunuz.
        </p>
      </div>

      {token ? (
        <section className="space-y-4">
          <h2 className="text-sm font-bold text-white uppercase tracking-wide flex items-center gap-1.5">
            <Bot className="w-4 h-4 text-[#F59E0B]" /> Kişisel AI Botunuz
          </h2>
          <PersonalBotPanel />
        </section>
      ) : (
        <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5 text-center">
          <p className="text-xs text-gray-400">
            Kişisel AI Bot durumunuzu, bakiyenizi ve işlem günlüğünüzü görmek için giriş yapmalısınız.
          </p>
        </div>
      )}
    </div>
  );
}
