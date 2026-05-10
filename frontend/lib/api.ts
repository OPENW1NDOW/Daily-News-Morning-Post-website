import type { NewsItem, Category, AdminStatus } from "./types"

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? ""

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, init)
  if (res.status === 404) return [] as unknown as T
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ ok: boolean }>("/api/health"),

  getCategories: () => request<Category[]>("/api/categories"),

  getNews: (params: { date?: string; category?: string }) => {
    const q = new URLSearchParams()
    if (params.date) q.set("date", params.date)
    if (params.category) q.set("category", params.category)
    return request<NewsItem[]>(`/api/news?${q}`)
  },

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

  getStatus: () => request<AdminStatus>("/api/admin/status"),

  triggerRefresh: () =>
    request<{ status: string; message: string }>("/api/admin/refresh", { method: "POST" }),
}
