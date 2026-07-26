"use client";

import React from "react";
import { Clock, ShieldAlert } from "lucide-react";

const LEGAL_LINKS = [
  { label: "Gizlilik Sözleşmesi", href: "#gizlilik-sozlesmesi" },
  { label: "Kullanıcı Sözleşmesi", href: "#kullanici-sozlesmesi" },
  { label: "KVKK Aydınlatma Metni", href: "#kvkk-aydinlatma" },
  { label: "Sorumluluk Reddi (YTD)", href: "#sorumluluk-reddi" },
];

export default function Footer() {
  return (
    <footer className="border-t border-[#242B35] bg-[#0B0E14] mt-10">
      {/* 15 Dakika Gecikmeli Veri Uyarı Bandı */}
      <div className="bg-[#F59E0B]/10 border-b border-[#F59E0B]/20 px-4 py-2.5">
        <div className="max-w-6xl mx-auto flex items-center gap-2 text-[11px] text-[#F59E0B]">
          <Clock className="w-3.5 h-3.5 shrink-0" />
          <span>
            Tüm veriler Borsa İstanbul kuralları gereği en az <strong>15 dakika gecikmelidir</strong> ve yalnızca simülasyon
            amaçlıdır. Gerçek zamanlı yatırım kararı almak için kullanılamaz.
          </span>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="flex items-start gap-2 mb-4">
          <ShieldAlert className="w-4 h-4 text-[#F43F5E] shrink-0 mt-0.5" />
          <p className="text-[11px] text-gray-500 leading-relaxed">
            Bu platform yalnızca eğitim ve simülasyon amaçlıdır; SPK lisanslı bir aracı kurum değildir. Hiçbir içerik
            yatırım tavsiyesi niteliği taşımaz. Gerçek para veya gerçek menkul kıymet işlemi yapılmaz.
          </p>
        </div>

        <div className="flex flex-wrap gap-x-5 gap-y-2 mb-5">
          {LEGAL_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="text-[11px] text-gray-400 hover:text-[#F59E0B] transition"
            >
              {link.label}
            </a>
          ))}
        </div>

        <div className="pt-4 border-t border-[#242B35] flex flex-col sm:flex-row items-center justify-between gap-2">
          <p className="text-[10px] text-gray-600">
            © {new Date().getFullYear()} BIST Simülasyonu & Yapay Zeka Trader. Tüm hakları saklıdır.
          </p>
          <p className="text-[10px] text-gray-600">Design by Eyüphan İpek Hazretleri (ks)</p>
        </div>
      </div>
    </footer>
  );
}
