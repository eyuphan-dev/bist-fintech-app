"use client";

import React, { useState } from "react";
import { Settings, KeyRound, Check, AlertCircle, User as UserIcon, RefreshCw } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";
import PushNotificationSettings from "../components/PushNotificationSettings";
import ReferralWidget from "../components/ReferralWidget";
import ProfileVisibilityWidget from "../components/ProfileVisibilityWidget";

export default function SettingsPage() {
  const { token, user, loading: authLoading } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    // Eşleşme kontrolü sunucuya gitmeden burada yapılır — gereksiz istek atmamak
    // ve kullanıcıya anında geri bildirim vermek için.
    if (newPassword !== confirmPassword) {
      setError("Yeni şifreler birbiriyle eşleşmiyor.");
      return;
    }
    if (newPassword.length < 6) {
      setError("Yeni şifre en az 6 karakter olmalıdır.");
      return;
    }
    if (newPassword === currentPassword) {
      setError("Yeni şifre mevcut şifreyle aynı olamaz.");
      return;
    }

    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/auth/change-password`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setSuccess(data.message || "Şifreniz güncellendi.");
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
      } else if (res.status === 429) {
        setError("Çok fazla deneme yaptınız. Lütfen bir dakika bekleyin.");
      } else {
        const data = await res.json().catch(() => null);
        setError(data?.detail || "Şifre güncellenemedi.");
      }
    } catch {
      setError("Sunucuya ulaşılamadı. Bağlantınızı kontrol edin.");
    } finally {
      setBusy(false);
    }
  };

  // Önce loading: token localStorage'dan okunurken !token'a bakmak, giriş yapmış
  // kullanıcıya bir an "giriş yapın" ekranı gösterirdi (bkz. app/page.tsx).
  if (authLoading) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center">
        <RefreshCw className="w-10 h-10 text-[#10B981] animate-spin mb-4" />
        <p className="text-gray-400 font-medium">Yükleniyor...</p>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 text-center">
          <p className="text-xs text-gray-400">Ayarlara erişmek için giriş yapmalısınız.</p>
        </div>
      </div>
    );
  }

  const inputClass =
    "w-full bg-[#0B0E14] border border-[#242B35] rounded-lg px-3 py-2.5 text-sm text-white outline-none focus:border-[#10B981]/50 transition";

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Settings className="w-5 h-5 text-[#F59E0B]" /> Hesap Ayarları
        </h1>
      </div>

      {/* Hesap bilgisi */}
      <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5">
        <div className="flex items-center gap-2 mb-3">
          <UserIcon className="w-4 h-4 text-gray-500" />
          <h2 className="text-xs font-bold text-white uppercase tracking-wide">Hesap Bilgileri</h2>
        </div>
        <div className="space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-gray-500">Kullanıcı adı</span>
            <span className="text-white font-semibold">@{user?.username}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">E-posta</span>
            <span className="text-white font-semibold">{user?.email ?? "—"}</span>
          </div>
        </div>
      </div>

      <ProfileVisibilityWidget />

      {/* Anlık bildirimler */}
      <ReferralWidget />

      <PushNotificationSettings />

      {/* Şifre değiştirme */}
      <form onSubmit={submit} className="bg-[#151921] border border-[#242B35] rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2">
          <KeyRound className="w-4 h-4 text-[#F59E0B]" />
          <h2 className="text-xs font-bold text-white uppercase tracking-wide">Şifre Değiştir</h2>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="current-password" className="text-[11px] text-gray-400 font-medium">
            Mevcut şifreniz
          </label>
          <input
            id="current-password"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className={inputClass}
            required
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="new-password" className="text-[11px] text-gray-400 font-medium">
            Yeni şifre <span className="text-gray-600">(en az 6 karakter)</span>
          </label>
          <input
            id="new-password"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className={inputClass}
            required
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="confirm-password" className="text-[11px] text-gray-400 font-medium">
            Yeni şifre (tekrar)
          </label>
          <input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className={inputClass}
            required
          />
        </div>

        {error && (
          <div className="flex items-start gap-2 bg-[#F43F5E]/10 border border-[#F43F5E]/30 rounded-lg px-3 py-2.5">
            <AlertCircle className="w-3.5 h-3.5 text-[#F43F5E] shrink-0 mt-0.5" />
            <p className="text-[11px] text-[#F43F5E]">{error}</p>
          </div>
        )}

        {success && (
          <div className="flex items-start gap-2 bg-[#10B981]/10 border border-[#10B981]/30 rounded-lg px-3 py-2.5">
            <Check className="w-3.5 h-3.5 text-[#10B981] shrink-0 mt-0.5" />
            <p className="text-[11px] text-[#10B981]">{success}</p>
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full bg-[#10B981] hover:bg-[#0EA271] text-[#0B0E14] font-bold text-sm py-2.5 rounded-lg transition disabled:opacity-50"
        >
          {busy ? "Güncelleniyor..." : "Şifreyi Güncelle"}
        </button>

        <p className="text-[10px] text-gray-600 border-t border-[#242B35] pt-3">
          Şifrenizi değiştirdikten sonra diğer cihazlardaki açık oturumlarınız süresi
          dolana kadar açık kalmaya devam eder.
        </p>
      </form>
    </div>
  );
}
