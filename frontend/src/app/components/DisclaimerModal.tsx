"use client";

import React, { useState } from "react";
import { Shield, AlertTriangle, CheckCircle, ChevronDown, ChevronUp } from "lucide-react";

interface DisclaimerModalProps {
  /** Kullanıcı "Okudum, Onaylıyorum" seçeneğini işaretleyip formu gönderince çağrılır. */
  onAccept: () => void;
  /** Modal kapatılmak istenince çağrılır (isteğe bağlı, varsa çarpı butonu gösterilir). */
  onClose?: () => void;
}

/**
 * MODÜL 3 — Yasal Sorumluluk Reddi, KVKK ve Feragatname Bileşeni
 *
 * Kullanıcı kayıt olurken veya ilk sanal işlemini yaparken bu bileşen gösterilir.
 * Checkbox işaretlenmeden onay butonu aktif olmaz.
 *
 * Kullanım:
 *   <DisclaimerModal onAccept={() => handleRegister()} onClose={() => setShowDisclaimer(false)} />
 */
export default function DisclaimerModal({ onAccept, onClose }: DisclaimerModalProps) {
  const [accepted, setAccepted] = useState(false);
  const [showFullText, setShowFullText] = useState(false);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-2xl bg-gray-950 border border-gray-800 rounded-2xl overflow-hidden">

        {/* ── Başlık ────────────────────────────────────────────────────── */}
        <div className="bg-gradient-to-r from-amber-500/10 to-orange-500/10 border-b border-amber-500/20 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Shield className="w-6 h-6 text-amber-400 shrink-0" />
            <div>
              <h2 className="text-base font-bold text-white">Kullanıcı Sözleşmesi & Feragatname</h2>
              <p className="text-xs text-amber-400/80 mt-0.5">Devam etmeden önce lütfen okuyunuz</p>
            </div>
          </div>
          {onClose && (
            <button onClick={onClose} className="text-gray-500 hover:text-white transition text-lg leading-none">✕</button>
          )}
        </div>

        {/* ── Uyarı Banner ───────────────────────────────────────────────── */}
        <div className="bg-rose-500/10 border-b border-rose-500/20 px-6 py-3 flex items-start space-x-2">
          <AlertTriangle className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
          <p className="text-xs text-rose-300 leading-relaxed">
            <strong>UYARI:</strong> Bu platform yalnızca eğitim ve simülasyon amaçlıdır.
            Gerçek yatırım tavsiyesi verilmez. Seans saatlerinde veriler en az 15 dakika gecikmeli olabilir.
          </p>
        </div>

        <div className="px-6 py-5 space-y-5 max-h-[60vh] overflow-y-auto">

          {/* ── Önemli Maddeler ────────────────────────────────────────────── */}
          <div className="space-y-3">
            {[
              {
                icon: "📊",
                title: "Yatırım Tavsiyesi Değildir (YTD)",
                body: "Bu sitedeki hiçbir grafik, algoritma veya yapay zeka tahmini, 6362 sayılı Sermaye Piyasası Kanunu (SPK) ve ilgili mevzuat kapsamında yatırım danışmanlığı hizmeti niteliği taşımaz. Platform, Sermaye Piyasası Kurulu (SPK) lisanslı bir aracı kurum değildir."
              },
              {
                icon: "🎮",
                title: "Tamamen Simülasyon Ortamı",
                body: "Platform gerçek bir aracı kurum veya banka değildir. Herhangi bir para yatırma, para çekme veya gerçek menkul kıymet alım-satım işlemi gerçekleştirilemez. Tüm bakiyeler ve işlemler tamamen hayali, sanal verilerden oluşmaktadır."
              },
              {
                icon: "⏱️",
                title: "Gecikmeli Veri — Anlık Karar Almaya Uygun Değil",
                body: "Platformda gösterilen fiyat verileri en az 15 dakika gecikmelidir. Bu veriler; anlık alım-satım kararı almak, piyasa takibi yapmak veya profesyonel yatırım analizi için kullanılamaz ve kullanılmamalıdır."
              },
              {
                icon: "⚖️",
                title: "Tam Sorumluluk Reddi",
                body: "Kullanıcı, platformdaki yapay zeka botu çıktılarını, grafikleri veya herhangi bir veriyi referans alarak gerçek piyasada işlem yapar ve zarara uğrarsa; platform sahiplerini, geliştiricilerini, sunucu sağlayıcılarını ve kullanılan yapay zeka modellerini hiçbir koşulda maddi veya manevi tazminat yükümlülüğü altına sokamaz."
              },
              {
                icon: "🔒",
                title: "KVKK — Kişisel Verilerin Korunması",
                body: "6698 sayılı Kişisel Verilerin Korunması Kanunu (KVKK) kapsamında: Kullanıcıya ait e-posta adresi ve platform içi işlem verileri yalnızca hesap güvenliği, oturum yönetimi ve istatistiksel simülasyon işlevleri için saklanır. Veriler üçüncü şahıslarla paylaşılmaz, reklam amaçlı kullanılmaz ve kullanıcı talep ettiğinde silinir."
              },
            ].map((item, i) => (
              <div key={i} className="bg-gray-900/60 border border-gray-800 rounded-xl p-4">
                <div className="flex items-start space-x-3">
                  <span className="text-xl shrink-0">{item.icon}</span>
                  <div>
                    <h4 className="text-sm font-bold text-white mb-1">{item.title}</h4>
                    <p className="text-xs text-gray-400 leading-relaxed">{item.body}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* ── Tam Yasal Metin (Akordiyon) ────────────────────────────────── */}
          <div className="border border-gray-800 rounded-xl overflow-hidden">
            <button
              onClick={() => setShowFullText(v => !v)}
              className="w-full flex items-center justify-between px-4 py-3 text-xs text-gray-400 hover:text-white transition bg-gray-900/40 hover:bg-gray-800/40"
            >
              <span className="font-semibold">Tam Hukuki Metin — Sorumluluk Reddi & Feragatname</span>
              {showFullText ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            {showFullText && (
              <div className="px-4 py-4 text-[11px] text-gray-500 leading-relaxed space-y-3 bg-gray-950/60">
                <p><strong className="text-gray-300">MADDE 1 — Taraflar ve Kapsam</strong><br />
                İşbu Kullanıcı Sözleşmesi ve Sorumluluk Reddi Feragatnamesi ("Sözleşme"), bir tarafta platform sahipleri ve geliştiricileri ("Platform"), diğer tarafta platformu kullanan gerçek veya tüzel kişi ("Kullanıcı") arasında akdedilmiştir. Kullanıcı, platforma kayıt olarak işbu Sözleşme'nin tamamını okuduğunu, anladığını ve kabul ettiğini beyan eder.</p>

                <p><strong className="text-gray-300">MADDE 2 — Yatırım Tavsiyesi Değildir</strong><br />
                Platformda sunulan grafik verileri, teknik analiz göstergeleri, yapay zeka tahminleri ve simülasyon botunun kararları hiçbir koşulda 6362 sayılı Sermaye Piyasası Kanunu kapsamında yatırım danışmanlığı, portföy yönetimi veya yatırım tavsiyesi olarak yorumlanamaz. Platform, Sermaye Piyasası Kurulu (SPK) nezdinde herhangi bir lisansa sahip değildir.</p>

                <p><strong className="text-gray-300">MADDE 3 — Simülasyon ve Hayali Bakiye</strong><br />
                Platform, gerçek bir aracı kurum, banka veya finans kuruluşu değildir. Kullanıcıya tanınan tüm bakiyeler hayalidir; herhangi bir para yatırma veya çekme işlemi gerçekleştirilmez. Gerçekleştirilen alım-satım işlemleri tamamen sanal olup gerçek sermaye piyasasında herhangi bir hukuki veya mali sonuç doğurmaz.</p>

                <p><strong className="text-gray-300">MADDE 4 — Gecikmeli Piyasa Verisi</strong><br />
                Platformda gösterilen tüm piyasa verileri (fiyat, hacim, teknik göstergeler) gerçek zamanlı değildir ve en az 15 (on beş) dakika gecikmeli olabilir. Kullanıcı, bu verileri gerçek zamanlı yatırım kararı almak amacıyla kullanmayacağını, platformun bu amaçla tasarlanmadığını kabul ve taahhüt eder.</p>

                <p><strong className="text-gray-300">MADDE 5 — Sorumluluk Reddi ve Hak Mahrumiyeti</strong><br />
                Kullanıcı, platformdaki yapay zeka botu çıktılarını, grafikleri, teknik göstergeleri veya herhangi bir içeriği referans alarak ve/veya bu içeriklere dayanarak gerçek sermaye piyasasında işlem yapar ve bu işlemler nedeniyle maddi veya manevi zarara uğrarsa; Platform sahiplerini, yöneticilerini, çalışanlarını, geliştiricilerini, sunucu sağlayıcılarını ve platformda kullanılan yapay zeka modellerini ve servis sağlayıcılarını hiçbir koşulda, hiçbir hukuki yol aracılığıyla (icra, dava, arabuluculuk, şikayet vb.) sorumlu tutamayacağını, tazminat talebinde bulunmayacağını <strong>gayrikabili rücu olarak</strong> kabul, beyan ve taahhüt eder.</p>

                <p><strong className="text-gray-300">MADDE 6 — KVKK ve Kişisel Veri İşleme</strong><br />
                6698 sayılı Kişisel Verilerin Korunması Kanunu ("KVKK") uyarınca Kullanıcı, e-posta adresi ve platform içi işlem kayıtlarının yalnızca hesap güvenliği, oturum yönetimi ve simülasyon istatistikleri amacıyla işlendiğini öğrenmiş ve bu işlemeye <strong>açık rıza</strong> gösterdiğini kabul eder. Veriler üçüncü şahıslarla paylaşılmayacak, reklam amacıyla kullanılmayacaktır. Kullanıcı, KVKK'nın 11. maddesi kapsamındaki haklarını (erişim, düzeltme, silme) yazılı başvuru yoluyla her zaman kullanabilir.</p>

                <p><strong className="text-gray-300">MADDE 7 — Uygulanacak Hukuk ve Yetki</strong><br />
                İşbu Sözleşme Türk Hukuku'na tabidir. Sözleşme'den doğan uyuşmazlıklarda İstanbul Mahkemeleri ve İcra Daireleri yetkilidir.</p>
              </div>
            )}
          </div>
        </div>

        {/* ── Onay Kutusu + Buton ────────────────────────────────────────── */}
        <div className="border-t border-gray-800 bg-gray-950 px-6 py-5 space-y-4">
          <label className="flex items-start space-x-3 cursor-pointer group">
            <div className="relative mt-0.5 shrink-0">
              <input
                type="checkbox"
                id="terms-accept"
                checked={accepted}
                onChange={e => setAccepted(e.target.checked)}
                className="sr-only"
              />
              <div
                onClick={() => setAccepted(v => !v)}
                className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all duration-150
                  ${accepted
                    ? "bg-emerald-500 border-emerald-500"
                    : "bg-transparent border-gray-600 group-hover:border-emerald-400"
                  }`}
              >
                {accepted && <CheckCircle className="w-3.5 h-3.5 text-white" />}
              </div>
            </div>
            <p className="text-xs text-gray-300 leading-relaxed">
              <strong className="text-white">Kullanıcı Sözleşmesi</strong>, <strong className="text-white">KVKK Aydınlatma Metni</strong> ve <strong className="text-white">Sorumluluk Reddi Feragatnamesi</strong>'ni okudum, anladım. Bu platformun tamamen bir{" "}
              <span className="text-amber-400 font-bold">simülasyon</span>{" "}
              olduğunu, buradaki verilerle yapacağım gerçek yatırımlardan doğacak her türlü maddi/manevi zarardan tamamen{" "}
              <span className="text-amber-400 font-bold">kendimin sorumlu olduğumu</span>{" "}
              ve platform sahiplerinden hiçbir hak/tazminat talep etmeyeceğimi{" "}
              <span className="text-rose-400 font-bold">gayrikabili rücu</span>{" "}
              KABUL EDİYORUM.
            </p>
          </label>

          <button
            onClick={onAccept}
            disabled={!accepted}
            className={`w-full py-3 rounded-xl font-bold text-sm transition-all duration-200
              ${accepted
                ? "bg-emerald-500 hover:bg-emerald-400 text-gray-950 active:scale-[0.98]"
                : "bg-gray-800 text-gray-600 cursor-not-allowed"
              }`}
          >
            {accepted ? "✓ Okudum, Onaylıyorum — Devam Et" : "Lütfen Onay Kutusunu İşaretleyin"}
          </button>

          <p className="text-center text-[10px] text-gray-600">
            Kayıt olarak bu sözleşmeyi kalıcı olarak kabul etmiş sayılırsınız.
          </p>
        </div>

      </div>
    </div>
  );
}
