"use client";

import React, { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { HelpCircle, X } from "lucide-react";

interface HelpContent {
  title: string;
  sections: { heading: string; body: string }[];
}

/** Route'a göre uygun yardım içeriğini üretir (usePathname tabanlı). */
function getHelpContent(pathname: string): HelpContent {
  if (pathname.startsWith("/hisse/")) {
    return {
      title: "Derin Bilanço Analizi Rehberi",
      sections: [
        {
          heading: "Piotroski F-Skoru Nedir?",
          body: "0-9 arası puanlanan finansal sağlamlık testidir. Kârlılık, borç yapısı ve verimlilik kriterlerine göre hesaplanır. 7-9 arası güçlü, 0-3 arası zayıf finansal yapıyı gösterir.",
        },
        {
          heading: "Makul Değer (Fair Value)",
          body: "Graham formülü (√(22.5 × Hisse Başı Kâr × Defter Değeri)) ile hesaplanan teorik değerdir. Güncel fiyatın altındaysa hisse potansiyel olarak ucuz görünür; bu bir yatırım tavsiyesi değildir.",
        },
        {
          heading: "Katılım Endeksi Uygunluğu",
          body: "Şirketin faaliyet konusu ve finansal oranlarının (borç/varlık, faiz geliri oranı vb.) Katılım Finans kriterlerine uygunluğunu gösterir. Uygun olsa dahi bir 'Arınma Oranı' önerilebilir.",
        },
      ],
    };
  }

  if (pathname.startsWith("/bot")) {
    return {
      title: "Yapay Zeka Trader (Quant Bot) Rehberi",
      sections: [
        {
          heading: "Bot Nasıl Çalışır?",
          body: "Bot yalnızca BİST seans saatlerinde (hafta içi 10:00-18:15) çalışır. RSI, MACD ve hareketli ortalamalar gibi teknik göstergeleri hesaplayarak AL/SAT/BEKLE kararı üretir.",
        },
        {
          heading: "Sanal İşlemler",
          body: "Botun tüm alım-satımları 100.000 TL hayali bakiye ile simüle edilir. Gerçek para veya gerçek borsa işlemi söz konusu değildir.",
        },
        {
          heading: "Performans Karşılaştırması",
          body: "Bot vs BİST 100 grafiği, botun stratejisinin piyasa ortalamasına göre ne kadar başarılı olduğunu gösterir.",
        },
      ],
    };
  }

  if (pathname.startsWith("/fonlar")) {
    return {
      title: "TEFAS Yatırım Fonları Rehberi",
      sections: [
        {
          heading: "TEFAS Nedir?",
          body: "Türkiye Elektronik Fon Alım Satım Platformu, yatırım fonlarının günlük fiyat ve getiri verilerinin toplandığı resmi platformdur.",
        },
        {
          heading: "Risk Seviyesi (1-7)",
          body: "1 en düşük, 7 en yüksek riski ifade eder. Risk seviyesi yükseldikçe potansiyel getiri ve potansiyel kayıp da artar.",
        },
        {
          heading: "Katılım Fonları",
          body: "Faizsiz finans prensiplerine uygun olarak yönetilen, kira sertifikası ve katılım endeksi hisselerine yatırım yapan fonlardır.",
        },
      ],
    };
  }

  return {
    title: "BIST Simülasyonu — Genel Bakış",
    sections: [
      {
        heading: "Platform Nedir?",
        body: "100.000 TL hayali bakiye ile Borsa İstanbul hisselerinde sanal alım-satım yapabileceğiniz, arkadaşlarınızla yarışabileceğiniz bir simülasyon platformudur.",
      },
      {
        heading: "Sanal Portföy Kuralları (Paper Trading)",
        body: "Tüm işlemler tamamen hayalidir; gerçek para veya gerçek menkul kıymet hareketi yoktur. Fiyatlar Borsa İstanbul kuralları gereği en az 15 dakika gecikmelidir.",
      },
      {
        heading: "Yatırım Tavsiyesi Değildir",
        body: "Platformdaki hiçbir gösterge, skor veya bot kararı SPK mevzuatı kapsamında yatırım danışmanlığı niteliği taşımaz.",
      },
    ],
  };
}

const STORAGE_KEY = "onboarding_help_seen_v1";

export default function OnboardingHelpModal() {
  const pathname = usePathname() || "/";
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const seen = localStorage.getItem(STORAGE_KEY);
    if (!seen) {
      setIsOpen(true);
      localStorage.setItem(STORAGE_KEY, "1");
    }
  }, []);

  const content = getHelpContent(pathname);

  return (
    <>
      {/* Yüzen Yardım Butonu */}
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-5 right-5 z-40 w-11 h-11 rounded-full bg-[#F59E0B] hover:bg-[#d98a08] text-[#0B0E14] shadow-lg shadow-black/40 flex items-center justify-center transition active:scale-95"
        title="Yardım"
      >
        <HelpCircle className="w-5 h-5" />
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="relative w-full max-w-md bg-[#151921] border border-[#242B35] rounded-2xl shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#242B35]">
              <h3 className="text-sm font-bold text-white">{content.title}</h3>
              <button onClick={() => setIsOpen(false)} className="text-gray-500 hover:text-white transition">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="px-5 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
              {content.sections.map((section, i) => (
                <div key={i}>
                  <h4 className="text-xs font-bold text-[#F59E0B] mb-1">{section.heading}</h4>
                  <p className="text-[11px] text-gray-400 leading-relaxed">{section.body}</p>
                </div>
              ))}
            </div>

            <div className="px-5 py-3 border-t border-[#242B35]">
              <button
                onClick={() => setIsOpen(false)}
                className="w-full bg-[#F59E0B] hover:bg-[#d98a08] text-[#0B0E14] font-bold text-xs py-2 rounded-lg transition"
              >
                Anladım
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
