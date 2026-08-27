"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Bell, BellOff, Check, AlertCircle, Smartphone, RefreshCw } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

/**
 * VAPID açık anahtarı base64url metin olarak gelir; `pushManager.subscribe`
 * ise ham bayt dizisi ister. Dönüşüm bu yüzden elle yapılır.
 */
function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  // Tampon açıkça ArrayBuffer olarak oluşturulur: `new Uint8Array(uzunluk)`
  // ArrayBufferLike üretir (SharedArrayBuffer da olabilir) ve applicationServerKey
  // yalnızca ArrayBuffer tabanlı bir görünüm kabul eder.
  const buffer = new ArrayBuffer(raw.length);
  const output = new Uint8Array(buffer);
  for (let i = 0; i < raw.length; i++) output[i] = raw.charCodeAt(i);
  return output;
}

function isStandalone(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (window.navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

function isIOS(): boolean {
  const ua = navigator.userAgent;
  return (
    /iPad|iPhone|iPod/.test(ua) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
  );
}

type State = "yukleniyor" | "desteklenmiyor" | "ios-kurulum-gerek" | "kapali" | "engellendi" | "acik";

/**
 * Push bildirimi açma/kapama.
 *
 * Alarm motoru sunucuda zaten çalışıyordu; eksik olan teslimattı — kullanıcı
 * uygulamayı açmazsa alarmından haberi olmuyordu. Burada tarayıcı aboneliği
 * kurulur ve sunucuya kaydedilir.
 *
 * iOS'un kendine özgü kuralı: Safari push aboneliğine YALNIZCA ana ekrana
 * eklenmiş (standalone) PWA'larda izin verir. Normal Safari sekmesinde izin
 * istemek bile başarısız olur ve hata mesajı açıklayıcı değildir. Bu yüzden
 * iOS'ta önce kurulum yönergesi gösterilir.
 */
export default function PushNotificationSettings() {
  const { token } = useAuth();
  const [state, setState] = useState<State>("yukleniyor");
  const [publicKey, setPublicKey] = useState<string | null>(null);
  const [deviceCount, setDeviceCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/push/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setState("desteklenmiyor");
        return;
      }
      const data = await res.json();
      setDeviceCount(data.device_count ?? 0);

      if (!data.configured) {
        setState("desteklenmiyor");
        return;
      }
      setPublicKey(data.public_key);

      if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
        // iOS'ta PushManager yalnızca standalone modda tanımlıdır; eksikliğini
        // "tarayıcı desteklemiyor" diye geçmek yanıltıcı olurdu.
        setState(isIOS() && !isStandalone() ? "ios-kurulum-gerek" : "desteklenmiyor");
        return;
      }
      if (isIOS() && !isStandalone()) {
        setState("ios-kurulum-gerek");
        return;
      }
      if (Notification.permission === "denied") {
        setState("engellendi");
        return;
      }

      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      setState(sub && Notification.permission === "granted" ? "acik" : "kapali");
    } catch {
      setState("desteklenmiyor");
    }
  }, [token]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const enable = async () => {
    if (!publicKey) return;
    setBusy(true);
    setMessage(null);
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setState(permission === "denied" ? "engellendi" : "kapali");
        setMessage({ kind: "err", text: "Bildirim izni verilmedi." });
        return;
      }

      const reg = await navigator.serviceWorker.ready;
      // Zaten bir abonelik varsa yenisini kurmadan onu kullan.
      const sub =
        (await reg.pushManager.getSubscription()) ||
        (await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(publicKey),
        }));

      const json = sub.toJSON() as { endpoint?: string; keys?: { p256dh?: string; auth?: string } };
      const res = await fetch(`${API_BASE}/push/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          endpoint: json.endpoint,
          p256dh: json.keys?.p256dh,
          auth: json.keys?.auth,
        }),
      });
      if (!res.ok) throw new Error("kayit basarisiz");

      const data = await res.json();
      setDeviceCount(data.device_count ?? 1);
      setState("acik");
      setMessage({ kind: "ok", text: "Bildirimler açıldı." });
    } catch {
      setMessage({ kind: "err", text: "Bildirimler açılamadı. Sayfayı yenileyip tekrar deneyin." });
    } finally {
      setBusy(false);
    }
  };

  const disable = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        const json = sub.toJSON() as { endpoint?: string; keys?: { p256dh?: string; auth?: string } };
        // Önce sunucudan sil: tarayıcı aboneliği önce iptal edilirse endpoint
        // elimizden gider ve sunucuda ölü bir kayıt kalırdı.
        await fetch(`${API_BASE}/push/unsubscribe`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({
            endpoint: json.endpoint,
            p256dh: json.keys?.p256dh ?? "",
            auth: json.keys?.auth ?? "",
          }),
        }).catch(() => {});
        await sub.unsubscribe();
      }
      setState("kapali");
      setDeviceCount((n) => Math.max(0, n - 1));
      setMessage({ kind: "ok", text: "Bu cihazda bildirimler kapatıldı." });
    } catch {
      setMessage({ kind: "err", text: "Bildirimler kapatılamadı." });
    } finally {
      setBusy(false);
    }
  };

  const sendTest = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const res = await fetch(`${API_BASE}/push/test`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json().catch(() => null);
      if (res.ok) {
        setMessage({ kind: "ok", text: `Deneme bildirimi ${data?.delivered ?? 1} cihaza gönderildi.` });
      } else {
        setMessage({ kind: "err", text: data?.detail || "Deneme bildirimi gönderilemedi." });
      }
    } catch {
      setMessage({ kind: "err", text: "Deneme bildirimi gönderilemedi." });
    } finally {
      setBusy(false);
    }
  };

  // Sunucuda push yapılandırılmamışsa çalışmayacak bir düğme göstermeyiz.
  if (state === "yukleniyor" || state === "desteklenmiyor") return null;

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5">
      <div className="flex items-center gap-2 mb-1">
        <Bell className="w-4 h-4 text-[#10B981]" />
        <h2 className="text-sm font-bold text-white">Anlık Bildirimler</h2>
      </div>
      <p className="text-[11px] text-gray-500 mb-4 leading-relaxed">
        Kurduğunuz fiyat alarmları, KAP bildirimleri ve AI sinyalleri uygulama
        kapalıyken de cihazınıza düşer.
      </p>

      {state === "ios-kurulum-gerek" && (
        <div className="flex items-start gap-2.5 bg-[#0B0E14] border border-[#242B35] rounded-xl p-3.5">
          <Smartphone className="w-4 h-4 text-[#F59E0B] shrink-0 mt-0.5" strokeWidth={1.5} />
          <p className="text-[11px] text-gray-400 leading-relaxed">
            iPhone ve iPad&apos;de bildirimler yalnızca uygulama{" "}
            <strong className="text-gray-200">ana ekrana eklendiğinde</strong> çalışır — bu
            Apple&apos;ın kuralı. Safari&apos;de Paylaş menüsünü açıp &quot;Ana Ekrana Ekle&quot;
            deyin, sonra uygulamayı ana ekrandaki simgesinden açıp bu sayfaya dönün.
          </p>
        </div>
      )}

      {state === "engellendi" && (
        <div className="flex items-start gap-2.5 bg-[#0B0E14] border border-[#242B35] rounded-xl p-3.5">
          <AlertCircle className="w-4 h-4 text-[#F43F5E] shrink-0 mt-0.5" strokeWidth={1.5} />
          <p className="text-[11px] text-gray-400 leading-relaxed">
            Bildirim izni bu cihazda <strong className="text-gray-200">reddedilmiş</strong>.
            Tarayıcı ayarlarından site izinlerine girip bildirimlere izin vermeniz gerekiyor;
            uygulama içinden tekrar sorulamıyor.
          </p>
        </div>
      )}

      {(state === "kapali" || state === "acik") && (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3 bg-[#0B0E14] border border-[#242B35] rounded-xl px-4 py-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-white">
                {state === "acik" ? "Bu cihazda açık" : "Bu cihazda kapalı"}
              </p>
              {deviceCount > 0 && (
                <p className="text-[10px] text-gray-500 mt-0.5">
                  Hesabınızda {deviceCount} kayıtlı cihaz var.
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={state === "acik" ? disable : enable}
              disabled={busy}
              className={`shrink-0 min-h-[40px] px-4 rounded-lg text-xs font-bold transition disabled:opacity-50 ${
                state === "acik"
                  ? "bg-[#242B35] text-gray-300 hover:text-white"
                  : "bg-[#10B981] text-[#0B0E14] hover:bg-[#059669]"
              }`}
            >
              {busy ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : state === "acik" ? (
                <span className="flex items-center gap-1.5">
                  <BellOff className="w-3.5 h-3.5" /> Kapat
                </span>
              ) : (
                <span className="flex items-center gap-1.5">
                  <Bell className="w-3.5 h-3.5" /> Aç
                </span>
              )}
            </button>
          </div>

          {state === "acik" && (
            <button
              type="button"
              onClick={sendTest}
              disabled={busy}
              className="w-full min-h-[40px] rounded-lg border border-[#242B35] text-xs font-semibold text-gray-400 hover:text-white transition disabled:opacity-50"
            >
              Deneme bildirimi gönder
            </button>
          )}
        </div>
      )}

      {message && (
        <p
          className={`text-[11px] mt-3 flex items-center gap-1.5 ${
            message.kind === "ok" ? "text-[#10B981]" : "text-[#F43F5E]"
          }`}
        >
          {message.kind === "ok" ? (
            <Check className="w-3.5 h-3.5 shrink-0" />
          ) : (
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          )}
          {message.text}
        </p>
      )}
    </div>
  );
}
