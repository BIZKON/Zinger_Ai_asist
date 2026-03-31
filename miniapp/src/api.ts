/**
 * API client for PersonalAI Mini App.
 * Sends Telegram initData for authentication.
 */

const API_BASE = import.meta.env.VITE_API_URL || "/api";

function getInitData(): string {
  return window.Telegram?.WebApp?.initData || "";
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const initData = getInitData();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(initData ? { "X-Telegram-Init-Data": initData } : {}),
  };

  const resp = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...headers, ...(options.headers as Record<string, string>) },
  });

  if (!resp.ok) {
    throw new Error(`API error: ${resp.status}`);
  }

  return resp.json();
}

// ── User API ──

export interface Profile {
  id: string;
  telegram_id: number;
  name: string | null;
  city: string | null;
  persona: string;
  voice_id: string;
  tier: string;
  timezone: string | null;
}

export interface Stats {
  messages: number;
  tasks_done: number;
  calls: number;
  files: number;
  tokens_used: number;
}

export interface MediaItem {
  id: string;
  file_type: string | null;
  original_filename: string | null;
  extracted_text: string | null;
  created_at: string | null;
}

export const api = {
  getProfile: () => request<Profile>("/user/profile"),

  updatePersona: (persona: string) =>
    request<{ ok: boolean }>("/user/persona", {
      method: "POST",
      body: JSON.stringify({ persona }),
    }),

  updateSettings: (data: Record<string, string | null>) =>
    request<{ ok: boolean }>("/user/settings", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getStats: (period: "week" | "month" = "month") =>
    request<Stats>(`/user/stats?period=${period}`),

  getMedia: (search = "", fileType = "all") =>
    request<{ items: MediaItem[] }>(
      `/user/media?search=${encodeURIComponent(search)}&file_type=${fileType}`
    ),
};
