"use client";

import React, { useEffect, useRef, useState } from "react";
import { PartyPopper, Star } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface Quest {
  id: string;
  isim: string;
  aciklama: string;
  puan: number;
  tamamlandi: boolean;
}

interface ToastData {
  buyukKutlama: boolean;
  title: string;
  body: string;
}

/**
 * Haftalık bir görev tamamlandığında (ya da haftanın TÜM görevleri
 * tamamlandığında) kısa süre görünüp kendiliğinden kapanan bir bildirim
 * gösterir -- görev/mağaza sayfalarına gitmeden de fark edilsin diye
 * layout.tsx'te uygulama genelinde monte edilir.
 *
 * Sayfa ilk yüklendiğinde geçmişte zaten tamamlanmış görevler için toast
 * ATILMAZ -- yalnızca bu oturumda YENİ tamamlanan görevler bildirilir.
 * `baselineRef` bu yüzden ilk fetch'te sessizce dolduruluyor.
 *
 * İki tetikleyici var: `refreshTrigger` (işlem/al-sat gibi eylemler sonrası
 * anında kontrol) ve 30sn'lik periyodik yoklama (izleme listesi ekleme,
 * yorum yapma gibi refreshTrigger'ı tetiklemeyen eylemler de görev
 * tamamlayabildiği için -- bunlar için yedek ağ).
 */
export default function QuestCompletionToast() {
  const { token, refreshTrigger } = useAuth();
  const [toast, setToast] = useState<ToastData | null>(null);
  const baselineRef = useRef<Map<string, boolean> | null>(null);

  useEffect(() => {
    if (!token) {
      baselineRef.current = null;
      return;
    }

    const kontrolEt = async () => {
      try {
        const res = await fetch(`${API_BASE}/quests`, { headers: { Authorization: `Bearer ${token}` } });
        if (!res.ok) return;
        const quests: Quest[] = await res.json();
        if (quests.length === 0) return;

        if (!baselineRef.current) {
          baselineRef.current = new Map(quests.map((q) => [q.id, q.tamamlandi]));
          return;
        }

        const oncekiHepsiTamam = Array.from(baselineRef.current.values()).every(Boolean);
        const simdiHepsiTamam = quests.every((q) => q.tamamlandi);
        const yeniTamamlanan = quests.find((q) => q.tamamlandi && baselineRef.current!.get(q.id) === false);

        baselineRef.current = new Map(quests.map((q) => [q.id, q.tamamlandi]));

        if (simdiHepsiTamam && !oncekiHepsiTamam) {
          const toplamPuan = quests.reduce((s, q) => s + q.puan, 0);
          setToast({
            buyukKutlama: true,
            title: "Haftalık görevler tamamlandı!",
            body: `Bu hafta toplam ${toplamPuan} oyun puanı kazandın.`,
          });
        } else if (yeniTamamlanan) {
          setToast({
            buyukKutlama: false,
            title: "Görev tamamlandı!",
            body: `${yeniTamamlanan.isim} — +${yeniTamamlanan.puan} oyun puanı kazandın.`,
          });
        }
      } catch {
        // Arka plan bildirimi -- sessizce yut, sayfayi bozmasin.
      }
    };

    kontrolEt();
    const interval = setInterval(kontrolEt, 30000);
    return () => clearInterval(interval);
  }, [token, refreshTrigger]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4500);
    return () => clearTimeout(t);
  }, [toast]);

  if (!toast) return null;

  return (
    <div
      className={`fixed bottom-[calc(5.25rem+env(safe-area-inset-bottom))] md:bottom-6 left-1/2 -translate-x-1/2 z-50 w-[calc(100vw-2rem)] max-w-sm border rounded-xl px-4 py-3 flex items-start gap-2.5 ${
        toast.buyukKutlama ? "bg-[#F59E0B]/10 border-[#F59E0B]/30" : "bg-[#151921] border-[#242B35]"
      }`}
    >
      {toast.buyukKutlama ? (
        <PartyPopper className="w-4 h-4 text-[#F59E0B] shrink-0 mt-0.5" />
      ) : (
        <Star className="w-4 h-4 text-[#F59E0B] shrink-0 mt-0.5" />
      )}
      <div className="min-w-0">
        <p className="text-xs font-bold text-white">{toast.title}</p>
        <p className="text-[11px] text-gray-400 mt-0.5">{toast.body}</p>
      </div>
    </div>
  );
}
