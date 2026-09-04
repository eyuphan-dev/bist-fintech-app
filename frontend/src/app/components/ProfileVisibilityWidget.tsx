"use client";

import React, { useState } from "react";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

/**
 * Herkese açık profil sayfasının (bkz. /profil/[username]) rozet + en büyük
 * pozisyon vitrinini açıp kapatan anahtar. Liderlik tablosundaki kullanıcı adı
 * + toplam değer zaten her zaman herkese açıktır -- bu yalnızca EK vitrini
 * kontrol eder (bkz. backend main.py get_public_profile).
 */
export default function ProfileVisibilityWidget() {
  const { token, user } = useAuth();
  const [isPublic, setIsPublic] = useState(user?.profile_public ?? true);
  const [saving, setSaving] = useState(false);

  const toggle = async () => {
    if (!token || saving) return;
    const yeniDeger = !isPublic;
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/user/profile-visibility`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ profile_public: yeniDeger }),
      });
      if (res.ok) setIsPublic(yeniDeger);
    } catch (err) {
      console.error("Profil görünürlüğü güncellenemedi:", err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 min-w-0">
          {isPublic ? <Eye className="w-4 h-4 text-[#10B981] shrink-0" /> : <EyeOff className="w-4 h-4 text-gray-500 shrink-0" />}
          <div className="min-w-0">
            <h3 className="text-sm font-bold text-white">Herkese Açık Profil</h3>
            <p className="text-[11px] text-gray-500 mt-0.5">
              Açıkken diğer kullanıcılar profilinden rozetlerini ve en büyük pozisyonlarının
              ağırlık yüzdesini görebilir (adet/TL tutarı asla gösterilmez). Liderlik
              tablosundaki kullanıcı adı ve toplam değer bu ayardan bağımsız her zaman görünür.
            </p>
          </div>
        </div>
        <button
          onClick={toggle}
          disabled={saving}
          role="switch"
          aria-checked={isPublic}
          aria-label="Herkese açık profili aç/kapat"
          className={`shrink-0 w-12 h-7 rounded-full transition relative disabled:opacity-50 ${
            isPublic ? "bg-[#10B981]" : "bg-[#242B35]"
          }`}
        >
          {saving ? (
            <Loader2 className="w-4 h-4 animate-spin text-white absolute top-1.5 left-1/2 -translate-x-1/2" />
          ) : (
            <span
              className={`absolute top-1 w-5 h-5 rounded-full bg-white transition-all ${
                isPublic ? "left-6" : "left-1"
              }`}
            />
          )}
        </button>
      </div>
    </div>
  );
}
