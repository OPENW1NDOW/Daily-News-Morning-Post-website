import type { NewsItem, Category, AdminStatus } from "./types"
import { getToken } from "./auth"

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? ""

function authHeaders(init?: RequestInit): RequestInit {
  const token = getToken()
  if (!token) return init ?? {}
  const headers = new Headers(init?.headers)
  headers.set("Authorization", `Bearer ${token}`)
  return { ...init, headers }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, authHeaders(init))
  if (res.status === 404) return [] as unknown as T
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ ok: boolean }>("/api/health"),

  // 认证
  register: (username: string, password: string) =>
    request<{ token: string; user: { id: number; username: string } }>("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }),

  login: (username: string, password: string) =>
    request<{ token: string; user: { id: number; username: string } }>("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }),

  getMe: () => request<{ id: number; username: string }>("/api/auth/me"),

  // 新闻
  getCategories: (date?: string) => {
    const q = new URLSearchParams()
    if (date) q.set("date", date)
    return request<Category[]>(`/api/categories?${q}`)
  },

  getNews: (params: { date?: string; category?: string }) => {
    const q = new URLSearchParams()
    if (params.date) q.set("date", params.date)
    if (params.category) q.set("category", params.category)
    return request<NewsItem[]>(`/api/news?${q}`)
  },

  // 收藏
  addFavorite: (news_item_id: number) =>
    request<{ id: number }>("/api/favorites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ news_item_id }),
    }),

  removeFavorite: (news_item_id: number) =>
    request<void>(`/api/favorites/${news_item_id}`, { method: "DELETE" }),

  getFavorites: (page = 1) =>
    request<{ items: NewsItem[]; total: number; page: number; pages: number }>(
      `/api/favorites?page=${page}`
    ),

  // 管理
  getStatus: () => request<AdminStatus>("/api/admin/status"),

  triggerRefresh: () =>
    request<{ status: string; message: string }>("/api/admin/refresh", { method: "POST" }),
}
