export interface NewsItem {
  id: number
  date: string
  category: string
  importance: number
  title: string
  summary: string | null
  full_summary: string | null
  viewpoints: { view: string; source: string }[] | null
  background: string | null
  source_links: { name: string; url: string }[] | null
  is_favorited: boolean
  created_at: string
}

export interface Category {
  key: string
  name: string
  description: string
  count: number
}

export interface PipelineProgress {
  running: boolean
  step: string
  step_index: number
  total_steps: number
  categories_done: number
  total_categories: number
}

export interface AdminStatus {
  today_count: number
  pipeline_running: boolean
  last_run: { status: string; counts?: Record<string, number>; error?: string } | null
  sources: { key: string; name: string; enabled: boolean; last_status: string; last_fetched_at: string | null }[]
  progress: PipelineProgress | null
}

// ── Admin types ──

export interface UserProfile {
  id: number
  username: string
  is_admin: boolean
}

export interface PipelineRun {
  id: number
  started_at: string | null
  finished_at: string | null
  trigger: string
  status: string
  result: Record<string, number> | null
  error: string | null
}

export interface AdminDashboard {
  today_count: number
  user_count: number
  total_news: number
  sources_ok: number
  sources_failed: number
  sources_total: number
  category_distribution: { key: string; name: string; count: number }[]
  latest_pipeline: PipelineRun | null
  system: { llm_model: string; proxy_url: string; db_size_mb: number }
}

export interface SourceDetail {
  id: number
  key: string
  name: string
  url: string
  use_proxy: boolean
  enabled: boolean
  last_fetched_at: string | null
  last_status: string
}

export interface AdminUser {
  id: number
  username: string
  is_admin: boolean
  created_at: string | null
  favorite_count: number
}

export interface CategoryConfig {
  key: string
  name: string
  description: string
}

export interface SystemSettings {
  llm_api_key_masked: string
  llm_base_url: string
  llm_model: string
  proxy_url: string
}

export interface AdminNewsItem {
  id: number
  date: string
  category: string
  importance: number
  title: string
  summary: string | null
  created_at: string | null
}
