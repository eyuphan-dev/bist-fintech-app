"use client";

import React, { useState } from "react";
import { ShieldAlert, CheckCircle2, ChevronDown, ChevronUp, X } from "lucide-react";

interface LegalDisclaimerModalProps {
  /** Kullanıcı onay kutusunu işaretleyip devam ettiğinde çağrılır (kayıt/işlem akışını tetikler). */
  onAccept: () => void;
  onClose?: () => void;
}

/**
 * Zorunlu Kayıt/İşlem Onay Modali — Tam Yasal Sorumluluk Reddi (YTD) & Feragatname.
 * Obsidian Dark UI sistemi ile inşa edilmiştir. Checkbox işaretlenmeden onay
 * butonu pasif kalır.
 */
export default function LegalDisclaimerModal({ onAccept, onClose }: LegalDisclaimerModalProps) {
  const [accepted, setAccepted] = useState(false);
  const [showFullText, setShowFullText] = useState(false);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-2xl bg-[#151921] border border-[#242B35] rounded-2xl shadow-2xl overflow-hidden">
        <div className="bg-[#F59E0B]/10 border-b border-[#F59E0B]/20 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ShieldAlert className="w-6 h-6 text-[#F59E0B] shrink-0" />
            <div>
              <h2 className="text-base font-bold text-white">Yasal Sorumluluk Reddi & Feragatname</h2>
              <p className="text-xs text-[#F59E0B]/80 mt-0.5">Kayıt / işlem yapmadan önce lütfen okuyunuz</p>
            </div>
          </div>
          {onClose && (
            <button onClick={onClose} className="text-gray-500 hover:text-white transition">
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        <div className="bg-[#F43F5E]/10 border-b border-[#F43F5E]/20 px-6 py-3">
          <p className="text-xs text-[#F43F5E] leading-relaxed">
            <strong>UYARI:</strong> Bu platform yalnızca eğitim ve simülasyon amaçlıdır. Yatırım tavsiyesi verilmez (YTD).
            Veriler en az 15 dakika gecikmelidir.
          </p>
        </div>

        <div className="px-6 py-5 space-y-4 max-h-[55vh] overflow-y-auto">
          {[
            { title: "Yatırım Tavsiyesi Değildir (YTD)", body: "Platformdaki hiçbir gösterge, Piotroski skoru, makul değer hesaplaması, yapay zeka bot kararı veya grafik; SPK mevzuatı kapsamında yatırım danışmanlığı niteliği taşımaz." },
            { title: "Tamamen Simülasyon", body: "Tüm bakiyeler ve işlemler hayalidir. Gerçek para yatırma/çekme veya gerçek menkul kıymet alım-satımı yapılmaz." },
            { title: "Gecikmeli Veri", body: "Fiyat verileri en az 15 dakika gecikmelidir; anlık karar almak için kullanılamaz." },
            { title: "Tam Sorumluluk Reddi", body: "Kullanıcı, platform verilerine dayanarak gerçek piyasada işlem yapar ve zarara uğrarsa platform sahiplerinden hiçbir tazminat talep edemez." },
            { title: "KVKK Aydınlatma", body: "Kişisel veriler yalnızca hesap güvenliği ve simülasyon istatistikleri için işlenir, üçüncü şahıslarla paylaşılmaz." },
          ].map((item, i) => (
            <div key={i} className="bg-[#0B0E14] border border-[#242B35] rounded-xl p-4">
              <h4 className="text-sm font-bold text-white mb-1">{item.title}</h4>
              <p className="text-xs text-gray-400 leading-relaxed">{item.body}</p>
            </div>
          ))}

          <div className="border border-[#242B35] rounded-xl overflow-hidden">
            <button
              onClick={() => setShowFullText((v) => !v)}
              className="w-full flex items-center justify-between px-4 py-3 text-xs text-gray-400 hover:text-white transition bg-[#0B0E14]"
            >
              <span className="font-semibold">Tam Hukuki Metin</span>
              {showFullText ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            {showFullText && (
              <div className="px-4 py-4 text-[11px] text-gray-500 leading-relaxed space-y-3 bg-[#0B0E14]">
                <p>
                  İşbu Sözleşme, Platform sahipleri/geliştiricileri ile Kullanıcı arasında akdedilmiştir. Kullanıcı,
                  platforma kayıt olarak veya sanal işlem yaparak; verilerin 6362 sayılı Sermaye Piyasası Kanunu
                  kapsamında yatırım danışmanlığı olmadığını, tüm bakiyelerin hayali olduğunu, verilerin en az 15
                  dakika gecikmeli olduğunu ve platform sahiplerinden hiçbir koşulda tazminat talep etmeyeceğini
                  gayrikabili rücu olarak kabul eder. KVKK md. 11 kapsamındaki haklarını her zaman kullanabilir.
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-[#242B35] bg-[#151921] px-6 py-5 space-y-4">
          <label className="flex items-start gap-3 cursor-pointer group">
            <div
              onClick={() => setAccepted((v) => !v)}
              className={`mt-0.5 shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${
                accepted ? "bg-[#10B981] border-[#10B981]" : "bg-transparent border-[#242B35] group-hover:border-[#10B981]"
              }`}
            >
              {accepted && <CheckCircle2 className="w-3.5 h-3.5 text-white" />}
            </div>
            <p className="text-xs text-gray-300 leading-relaxed">
              <strong className="text-white">Kullanıcı Sözleşmesi</strong>, <strong className="text-white">KVKK Aydınlatma Metni</strong> ve{" "}
              <strong className="text-white">Sorumluluk Reddi Feragatnamesi</strong>'ni okudum, anladım ve tüm işlemlerin
              tamamen <span className="text-[#F59E0B] font-bold">simülasyon</span> olduğunu, doğacak zararlardan{" "}
              <span className="text-[#F59E0B] font-bold">kendimin sorumlu olduğumu</span> <span className="text-[#F43F5E] font-bold">gayrikabili rücu</span> kabul ediyorum.
            </p>
          </label>

          <button
            onClick={onAccept}
            disabled={!accepted}
            className={`w-full py-3 rounded-xl font-bold text-sm transition-all ${
              accepted
                ? "bg-[#10B981] hover:bg-[#0da271] text-[#0B0E14] shadow-lg shadow-[#10B981]/20 active:scale-[0.98]"
                : "bg-[#242B35] text-gray-600 cursor-not-allowed"
            }`}
          >
            {accepted ? "✓ Okudum, Onaylıyorum — Devam Et" : "Lütfen Onay Kutusunu İşaretleyin"}
          </button>
        </div>
      </div>
    </div>
  );
}
