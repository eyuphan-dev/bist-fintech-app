"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";

// Prod'da Vercel ortam değişkeni NEXT_PUBLIC_API_URL, Render'daki backend URL'ini
// gösterecek şekilde ayarlanmalıdır (örn. https://bist-simulasyonu-api.onrender.com/api).
// Tanımlı değilse yerel geliştirme backend'ine düşer.
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

interface User {
  id: number;
  username: string;
  email: string;
  virtual_balance: number;
  is_bot: boolean;
  terms_accepted: boolean;
  created_at: string;
}

interface AuthContextValue {
  token: string | null;
  user: User | null;
  loading: boolean;
  refreshTrigger: number;
  bumpRefresh: () => void;
  login: (username: string, password: string) => Promise<{ ok: boolean; message?: string }>;
  register: (username: string, email: string, password: string) => Promise<{ ok: boolean; message?: string }>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  useEffect(() => {
    const stored = localStorage.getItem("token");
    if (stored) {
      setToken(stored);
    } else {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!token) return;

    const fetchMe = async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          setUser(await res.json());
        } else {
          logout();
        }
      } catch (err) {
        console.error("Kimlik doğrulama kontrolü başarısız:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchMe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, refreshTrigger]);

  // Periyodik yenileme (fiyatlar, portföy vb. taze kalsın diye)
  useEffect(() => {
    if (!token) return;
    const interval = setInterval(() => setRefreshTrigger((p) => p + 1), 15000);
    return () => clearInterval(interval);
  }, [token]);

  const bumpRefresh = useCallback(() => setRefreshTrigger((p) => p + 1), []);

  const login = useCallback(async (username: string, password: string) => {
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (res.ok) {
        localStorage.setItem("token", data.access_token);
        setToken(data.access_token);
        return { ok: true };
      }
      return { ok: false, message: data.detail || "Kimlik doğrulama başarısız." };
    } catch {
      return { ok: false, message: "Sunucuya bağlanılamadı." };
    }
  }, []);

  const register = useCallback(async (username: string, email: string, password: string) => {
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password, terms_accepted: true }),
      });
      const data = await res.json();
      if (res.ok) return { ok: true };
      return { ok: false, message: data.detail || "Kayıt başarısız." };
    } catch {
      return { ok: false, message: "Sunucuya bağlanılamadı." };
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, loading, refreshTrigger, bumpRefresh, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
