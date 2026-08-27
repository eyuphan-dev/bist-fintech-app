"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Bell, TrendingUp, TrendingDown, Percent, Newspaper, Bot as BotIcon } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface NotificationItem {
  id: number;
  stock_symbol: string | null;
  notif_type: "PRICE_ABOVE" | "PRICE_BELOW" | "PCT_CHANGE" | "KAP" | "AI_SIGNAL";
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

const TYPE_ICON: Record<string, any> = {
  PRICE_ABOVE: TrendingUp,
  PRICE_BELOW: TrendingDown,
  PCT_CHANGE: Percent,
  KAP: Newspaper,
  AI_SIGNAL: BotIcon,
};

/** Navbar'daki bildirim zili: okunmamış sayısı 15sn'de bir tazelenir, tıklayınca son bildirimler açılır. */
export default function NotificationBell() {
  const { token, refreshTrigger } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<NotificationItem[] | null>(null);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const fetchUnreadCount = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/notifications/unread-count`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUnreadCount(data.count);
      }
    } catch (err) {
      console.error("Okunmamış bildirim sayısı alınamadı:", err);
    }
  };

  useEffect(() => {
    fetchUnreadCount();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, refreshTrigger]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleToggle = async () => {
    const willOpen = !open;
    setOpen(willOpen);
    if (willOpen && token) {
      try {
        const res = await fetch(`${API_BASE}/notifications`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) setNotifications(await res.json());
      } catch (err) {
        console.error("Bildirimler alınamadı:", err);
      }
    }
  };

  const handleMarkAllRead = async () => {
    if (!token) return;
    try {
      await fetch(`${API_BASE}/notifications/read-all`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      setUnreadCount(0);
      setNotifications((prev) => prev?.map((n) => ({ ...n, is_read: true })) ?? null);
    } catch (err) {
      console.error("Bildirimler okundu işaretlenemedi:", err);
    }
  };

  if (!token) return null;

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={handleToggle}
        className="relative bg-[#151921] border border-[#242B35] hover:bg-[#242B35] p-2 rounded-lg text-gray-400 hover:text-white transition min-w-[44px] min-h-[44px] md:min-w-0 md:min-h-0 flex items-center justify-center"
        title="Bildirimler"
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-1.5 -right-1.5 bg-[#F43F5E] text-white text-[9px] font-bold rounded-full min-w-[16px] h-[16px] flex items-center justify-center px-1">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 max-w-[90vw] bg-[#151921] border border-[#242B35] rounded-xl z-50 overflow-hidden">
          <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-[#242B35]">
            <span className="text-xs font-bold text-white">Bildirimler</span>
            {unreadCount > 0 && (
              <button onClick={handleMarkAllRead} className="text-[10px] text-[#4A87C7] hover:text-[#34d399] font-semibold">
                Tümünü okundu işaretle
              </button>
            )}
          </div>

          <div className="max-h-[360px] overflow-y-auto">
            {notifications === null ? (
              <p className="text-[11px] text-gray-500 text-center py-6">Yükleniyor...</p>
            ) : notifications.length === 0 ? (
              <p className="text-[11px] text-gray-500 text-center py-6">Henüz bildirim yok.</p>
            ) : (
              notifications.map((n) => {
                const Icon = TYPE_ICON[n.notif_type] || Bell;
                const content = (
                  <div
                    className={`flex items-start gap-2.5 px-3.5 py-3 border-b border-[#242B35] last:border-0 ${
                      n.is_read ? "" : "bg-[#4A87C7]/5"
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5 text-[#F59E0B] shrink-0 mt-0.5" />
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-semibold text-white leading-snug">{n.title}</p>
                      <p className="text-[10px] text-gray-500 mt-0.5 leading-snug">{n.message}</p>
                      <p className="text-[9px] text-gray-600 mt-1">
                        {new Date(n.created_at).toLocaleString("tr-TR")}
                      </p>
                    </div>
                    {!n.is_read && <span className="w-1.5 h-1.5 rounded-full bg-[#4A87C7] shrink-0 mt-1" />}
                  </div>
                );
                return n.stock_symbol ? (
                  <Link key={n.id} href={`/hisse/${n.stock_symbol}`} onClick={() => setOpen(false)}>
                    {content}
                  </Link>
                ) : (
                  <div key={n.id}>{content}</div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
