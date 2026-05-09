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
