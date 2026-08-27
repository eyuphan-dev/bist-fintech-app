"use client";

import React from "react";
import { X, Gauge, ShieldAlert, Scale, Crosshair, ListChecks, TriangleAlert } from "lucide-react";

interface AnalysisGuideModalProps {
  onClose: () => void;
}

const METRIC_CARDS = [
  {
    icon: Gauge,
    title: "Piotroski F-Skoru (0-9)",
    body: "Şirketin finansal sağlığındaki iyileşmeyi ölçer. 7-9 arası çok güçlü, 3 altı zayıf finansal yapıya işaret eder.",
  },
  {
    icon: ShieldAlert,
    title: "Altman Z-Skoru",
    body: "Şirketin finansal sıkıntı / iflas riskini ölçer (Güvenli Bölge, Gri Bölge, Riskli Bölge).",
  },
  {
    icon: Scale,
    title: "F/K ve PD/DD",
    body: "Hissenin ederine göre ucuz/pahalı oluşunu gösterir. Sektör ortalamasıyla kıyaslamak esastır.",
  },
  {
    icon: Scale,
    title: "Net Borç / FAVÖK",
    body: "Şirketin borcunu faaliyet kârıyla kaç yılda kapatabileceğini gösterir (2.5 altı idealdir).",
  },
  {
    icon: Crosshair,
    title: "Pivot & Destek/Direnç",
    body: "Fiyatın tepki verebileceği psikolojik ve teknik seviyelerdir.",
  },
];

const CHECKLIST_ITEMS = [
  "Tek bir metriğe bakarak karar vermeyin; temel ve teknik verileri harmanlayın.",
  "Şirketin sadece kârına değil, kasasına giren net nakit akışına bakın.",
  "Döviz yükümlülüğü ve faiz artışına karşı duyarlılığını (borçluluk oranını) kontrol edin.",
];

/**
 * "Derin Bilanço Analizi" sekmesindeki metriklerin ne anlama geldiğini açıklayan
 * eğitim amaçlı bilgi modalı. Backdrop tıklaması ve X ikonuyla kapanır.
 */
export default function AnalysisGuideModal({ onClose }: AnalysisGuideModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-lg bg-[#151921] border border-[#242B35] rounded-2xl overflow-hidden max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="bg-[#F59E0B]/10 border-b border-[#F59E0B]/20 px-5 py-4 flex items-center justify-between shrink-0">
          <h2 className="text-sm font-bold text-white">📊 Derin Bilanço & Finansal Analiz Rehberi</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition shrink-0" title="Kapat">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-5 overflow-y-auto">
          {/* Bölüm 1: Metrikler Ne Anlama Gelir? */}
          <div className="space-y-2">
            <h3 className="text-[11px] font-bold text-gray-400 uppercase tracking-wide">Metrikler Ne Anlama Gelir?</h3>
            {METRIC_CARDS.map((item, i) => {
              const Icon = item.icon;
              return (
                <div key={i} className="bg-[#0B0E14] border border-[#242B35] rounded-xl p-3 flex items-start gap-2.5">
                  <Icon className="w-4 h-4 text-[#F59E0B] shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-xs font-bold text-white">{item.title}</h4>
                    <p className="text-[11px] text-gray-400 leading-relaxed mt-0.5">{item.body}</p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Bölüm 2: Genel Olarak Nelere Dikkat Edilmeli? */}
          <div className="space-y-2">
            <h3 className="text-[11px] font-bold text-gray-400 uppercase tracking-wide flex items-center gap-1.5">
              <ListChecks className="w-3.5 h-3.5" /> Genel Olarak Nelere Dikkat Edilmeli?
            </h3>
            <div className="bg-[#0B0E14] border border-[#242B35] rounded-xl p-3 space-y-2">
              {CHECKLIST_ITEMS.map((text, i) => (
                <p key={i} className="text-[11px] text-gray-400 leading-relaxed flex items-start gap-2">
                  <span className="text-[#10B981] font-bold shrink-0">✓</span>
                  {text}
                </p>
              ))}
            </div>
          </div>

          {/* Bölüm 3: Zorunlu Yasal Uyarı */}
          <div className="bg-[#F43F5E]/10 border border-[#F43F5E]/30 rounded-xl p-3.5 flex items-start gap-2.5">
            <TriangleAlert className="w-4 h-4 text-[#F43F5E] shrink-0 mt-0.5" />
            <p className="text-[11px] text-[#F43F5E] leading-relaxed font-medium">
              <strong>⚠️ YASAL UYARI:</strong> Burada yer alan veri, skor, analiz ve yorumlar kesinlikle YATIRIM
              TAVSİYESİ DEĞİLDİR. Yalnızca bilgilendirme ve eğitim amacıyla sunulmaktadır. Yatırım kararlarınızı
              kendi araştırmalarınız ve yetkili yatırım danışmanınız doğrultusunda vermelisiniz.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
