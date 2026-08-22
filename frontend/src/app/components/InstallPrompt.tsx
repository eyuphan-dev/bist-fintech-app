"use client";

import React, { useEffect, useState } from "react";
import { Share, Plus, X, Download } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const DISMISS_KEY = "pwa-install-dismissed";

/** beforeinstallprompt tip tanımı — henüz standart TypeScript DOM tiplerinde yok. */
interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

/** Uygulama ana ekrandan (standalone) mı açılmış? */
function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    // iOS Safari standart display-mode sorgusunu desteklemez, kendi bayrağını kullanır.
    (window.navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

/**
 * iOS'ta Safari `beforeinstallprompt` olayını HİÇ tetiklemez; kullanıcı Paylaş
 * menüsünden "Ana Ekrana Ekle" demek zorundadır ve bunu kendiliğinden keşfeden
 * kullanıcı sayısı çok azdır. Bu yüzden iki ayrı yol izlenir:
 *
 *   - iOS Safari : elle yapılacak adımları anlatan bir bilgi kartı gösterilir.
 *   - Diğerleri  : tarayıcının kendi kurulum akışını başlatan gerçek bir buton.
 *
 * Kart yalnızca giriş yapılmışsa, uygulama tarayıcıda açıksa ve kullanıcı daha
 * önce kapatmadıysa görünür.
 */
export default function InstallPrompt() {
  const { token } = useAuth();
  const [mode, setMode] = useState<"ios" | "native" | null>(null);
  const [deferred, setDeferred] = useState<InstallPromptEvent | null>(null);

  useEffect(() => {
    if (isStandalone()) return;
    try {
      if (localStorage.getItem(DISMISS_KEY) === "1") return;
    } catch {
      // Gizli sekmede localStorage erişimi hata verebilir; kart yine gösterilir.
    }

    const ua = navigator.userAgent;
    // iPadOS 13+ kendini masaüstü Mac gibi tanıtır; dokunmatik nokta sayısı ayırt eder.
    const iOS =
      /iPad|iPhone|iPod/.test(ua) ||
      (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    // iOS'ta yalnızca Safari ana ekrana ekleyebilir; Chrome/Firefox/Edge ekleyemez.
    const iOSSafari = iOS && !/CriOS|FxiOS|EdgiOS|OPiOS/.test(ua);

    if (iOSSafari) {
      // Kullanıcı daha sayfayı görmeden kart açılmasın.
      const timer = setTimeout(() => setMode("ios"), 4000);
      return () => clearTimeout(timer);
    }

    const onPrompt = (e: Event) => {
      e.preventDefault(); // Tarayıcının kendi çubuğu yerine kendi kartımızı gösteririz.
      setDeferred(e as InstallPromptEvent);
      setMode("native");
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  const dismiss = () => {
    setMode(null);
    try {
      localStorage.setItem(DISMISS_KEY, "1");
    } catch {
      // Kalıcı olarak saklanamazsa en azından bu oturumda kapanır.
    }
  };

  const install = async () => {
    if (!deferred) return;
    await deferred.prompt();
    await deferred.userChoice;
    dismiss();
  };

  if (!token || !mode) return null;

  return (
    <div
      className="md:hidden fixed inset-x-3 z-40"
      // Aşağıdan yukarı sıralama: alt gezinme çubuğu (~3.75rem), yardım butonu
      // (5.5rem–8.25rem arası), sonra bu kart. 9.75rem her ikisini de temizler.
      style={{ bottom: "calc(9.75rem + env(safe-area-inset-bottom))" }}
      role="dialog"
      aria-label="Uygulamayı ana ekrana ekle"
    >
      <div className="bg-[#151921] border border-[#242B35] rounded-xl shadow-lg p-3.5">
        <div className="flex items-start gap-3">
          <span className="w-9 h-9 rounded-lg bg-[#10B981]/10 flex items-center justify-center shrink-0">
            <Download className="w-4 h-4 text-[#10B981]" strokeWidth={1.5} />
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-bold text-white">Ana ekrana ekle</p>
            <p className="text-[11px] text-gray-400 leading-relaxed mt-0.5">
              {mode === "ios" ? (
                <>
                  Paylaş <Share className="w-3 h-3 inline-block mx-0.5 -mt-0.5" /> menüsünü
                  açın, <strong className="text-gray-300">Ana Ekrana Ekle</strong>{" "}
                  <Plus className="w-3 h-3 inline-block mx-0.5 -mt-0.5" /> seçeneğine dokunun.
                </>
              ) : (
                <>Tam ekran, uygulama gibi çalışır — tarayıcı çubuğu olmadan.</>
              )}
            </p>
            {mode === "native" && (
              <button
                onClick={install}
                type="button"
                className="mt-2.5 w-full min-h-[40px] rounded-lg bg-[#10B981] text-[#0B0E14] text-xs font-bold active:bg-[#059669] transition"
              >
                Yükle
              </button>
            )}
          </div>
          <button
            onClick={dismiss}
            type="button"
            aria-label="Kapat"
            className="p-1.5 -m-1 min-w-[36px] min-h-[36px] flex items-center justify-center text-gray-500 hover:text-white transition shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
