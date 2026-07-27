import type {
  NewsItem, Category, AdminStatus, UserProfile, AdminDashboard,
  PipelineRun, SourceDetail, AdminUser, CategoryConfig, SystemSettings, AdminNewsItem,
  PipelineProgress, XAccount, XFollowingStatus,
} from "./types"
import { getToken, clearToken } from "./auth"

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
  if (!res.ok) {
    // token 过期或无效时清掉本地凭证，避免后续请求继续携带脏 token
    if (res.status === 401) clearToken()
    let msg = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body.detail) msg = body.detail
    } catch {}
    throw new Error(msg)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ ok: boolean }>("/api/health"),

  // 认证
  register: (username: string, password: string) =>
    request<{ token: string; user: UserProfile }>("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }),

  login: (username: string, password: string) =>
    request<{ token: string; user: UserProfile }>("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }),

  getMe: () => request<UserProfile>("/api/auth/me"),

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

  // ── Admin API ──

  // 仪表盘
  adminDashboard: () => request<AdminDashboard>("/api/admin/dashboard"),

  // 流水线
  adminTriggerPipeline: () =>
    request<{ status: string; message: string }>("/api/admin/pipeline/trigger", { method: "POST" }),
  adminPipelineStatus: () =>
    request<{ pipeline_running: boolean; progress: PipelineProgress | null; last_run: Record<string, unknown> | null }>("/api/admin/pipeline/status"),
  adminPipelineHistory: (page = 1) =>
    request<{ items: PipelineRun[]; total: number; page: number; pages: number }>(`/api/admin/pipeline/history?page=${page}`),

  // 数据源
  adminSources: () => request<SourceDetail[]>("/api/admin/sources"),
  adminUpdateSource: (id: number, data: Partial<SourceDetail>) =>
    request<SourceDetail>(`/api/admin/sources/${id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
    }),
  adminTestSource: (id: number) =>
    request<{ ok: boolean; status: number | null; error: string | null }>(`/api/admin/sources/${id}/test`, { method: "POST" }),

  // 新闻管理
  adminNews: (params: { date?: string; category?: string; page?: number }) => {
    const q = new URLSearchParams()
    if (params.date) q.set("date_str", params.date)
    if (params.category) q.set("category", params.category)
    if (params.page) q.set("page", String(params.page))
    return request<{ items: AdminNewsItem[]; total: number; page: number; pages: number }>(`/api/admin/news?${q}`)
  },
  adminGetNews: (id: number) => request<NewsItem>(`/api/admin/news/${id}`),
  adminUpdateNews: (id: number, data: Partial<NewsItem>) =>
    request<NewsItem>(`/api/admin/news/${id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
    }),
  adminDeleteNews: (id: number) =>
    request<{ ok: boolean }>(`/api/admin/news/${id}`, { method: "DELETE" }),

  // 用户管理
  adminUsers: () => request<AdminUser[]>("/api/admin/users"),
  adminToggleAdmin: (userId: number, isAdmin: boolean) =>
    request<{ ok: boolean }>(`/api/admin/users/${userId}/admin`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_admin: isAdmin }),
    }),

  // 板块管理
  adminCategories: () => request<CategoryConfig[]>("/api/admin/categories"),
  adminUpdateCategory: (key: string, data: Partial<CategoryConfig>) =>
    request<CategoryConfig>(`/api/admin/categories/${key}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
    }),

  // 系统设置
  adminSettings: () => request<SystemSettings>("/api/admin/settings"),
  adminUpdateSettings: (data: Partial<SystemSettings>) =>
    request<{ message: string }>("/api/admin/settings", {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
    }),

  // X Following
  adminXFollowingAccounts: () => request<XAccount[]>("/api/admin/x-following/accounts"),
  adminPatchXFollowingAccount: (id: number, data: { enabled: boolean }) =>
    request<XAccount>(`/api/admin/x-following/accounts/${id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
    }),
  adminSyncXFollowing: () =>
    request<{ status: string; count: number }>("/api/admin/x-following/sync", { method: "POST" }),
  adminXFollowingStatus: () => request<XFollowingStatus>("/api/admin/x-following/status"),
}
