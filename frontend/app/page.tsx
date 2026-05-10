"use client"

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { api } from "@/lib/api"
import { todayStr } from "@/lib/utils"
import type { NewsItem, Category, PipelineProgress } from "@/lib/types"
import { NewsDrawer } from "@/components/NewsDrawer"
import { CategoryTabs } from "@/components/CategoryTabs"
import { DateSwitcher } from "@/components/DateSwitcher"
import { NewsSkeleton } from "@/components/NewsSkeleton"
import { HeroCard } from "@/components/HeroCard"
import { SectionBlock } from "@/components/SectionBlock"
import { SamoyedAvatar } from "@/components/SamoyedAvatar"

function formatDateZH(d: string) {
  const [y, m, day] = d.split("-")
  const date = new Date(`${d}T00:00:00`)
  const weekday = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][date.getDay()]
  return `${y} 年 ${Number(m)} 月 ${Number(day)} 日 · ${weekday}`
}

function HomeContent() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [categories, setCategories] = useState<Category[]>([])
  const [itemsByCategory, setItemsByCategory] = useState<Record<string, NewsItem[]>>({})
  const [selected, setSelected] = useState<NewsItem | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [newsStatus, setNewsStatus] = useState<"loading" | "ok" | "empty" | "error">("loading")
  const [refreshing, setRefreshing] = useState(false)
  const [progress, setProgress] = useState<PipelineProgress | null>(null)
  const [activeTab, setActiveTab] = useState<string>("all")
  const [query, setQuery] = useState("")
  const autoTriggered = useRef(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const activeDate = searchParams.get("date") ?? todayStr()

  function setDate(d: string) {
    const p = new URLSearchParams(searchParams.toString())
    p.set("date", d)
    router.replace(`/?${p}`, { scroll: false })
  }

  const loadData = useCallback(async () => {
    if (!refreshing) setNewsStatus("loading")
    try {
      const cats = await api.getCategories()
      setCategories(cats)

      const results = await Promise.all(
        cats.map((c) =>
          api.getNews({ category: c.key, date: activeDate }).then((items) => [c.key, items] as const)
        )
      )
      const map: Record<string, NewsItem[]> = {}
      let total = 0
      for (const [key, items] of results) {
        map[key] = items
        total += items.length
      }
      setItemsByCategory(map)
      setNewsStatus(total === 0 ? "empty" : "ok")
    } catch {
      setNewsStatus("error")
    }
  }, [activeDate, refreshing])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Hero：全天 importance 最高的 1 条
  const { hero, sectionItems } = useMemo(() => {
    const all = Object.values(itemsByCategory).flat()
    if (all.length === 0) return { hero: null as NewsItem | null, sectionItems: {} as Record<string, NewsItem[]> }
    const hero = all.reduce((a, b) => (b.importance > a.importance ? b : a))
    const sectionItems: Record<string, NewsItem[]> = {}
    for (const [key, items] of Object.entries(itemsByCategory)) {
      sectionItems[key] = items.filter((it) => it.id !== hero.id)
    }
    return { hero, sectionItems }
  }, [itemsByCategory])

  // 搜索与 tab 过滤后的可见板块
  const visibleCategories = useMemo(() => {
    const q = query.trim().toLowerCase()
    return categories
      .filter((c) => (activeTab === "all" ? true : c.key === activeTab))
      .map((c) => {
        const items = sectionItems[c.key] ?? []
        const filtered = q
          ? items.filter(
              (it) =>
                it.title.toLowerCase().includes(q) ||
                (it.summary ?? "").toLowerCase().includes(q)
            )
          : items
        return { category: c, items: filtered }
      })
      .filter((x) => x.items.length > 0)
  }, [categories, sectionItems, activeTab, query])

  function handleTabChange(key: string) {
    setActiveTab(key)
    if (key !== "all") {
      requestAnimationFrame(() => {
        document.getElementById(`cat-${key}`)?.scrollIntoView({ behavior: "smooth", block: "start" })
      })
    } else {
      window.scrollTo({ top: 0, behavior: "smooth" })
    }
  }

  function openItem(item: NewsItem) {
    setSelected(item)
    setDrawerOpen(true)
  }

  function handleFavoriteToggle(id: number, nowFavorited: boolean) {
    setItemsByCategory((prev) => {
      const next: Record<string, NewsItem[]> = {}
      for (const [k, list] of Object.entries(prev)) {
        next[k] = list.map((it) => (it.id === id ? { ...it, is_favorited: nowFavorited } : it))
      }
      return next
    })
    if (selected?.id === id)
      setSelected((prev) => (prev ? { ...prev, is_favorited: nowFavorited } : prev))
  }

  // 统一轮询逻辑
  const startPolling = useCallback(() => {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      try {
        const st = await api.getStatus()
        if (st.progress) setProgress(st.progress)
        if (!st.pipeline_running) {
          stopPolling()
          setRefreshing(false)
          setProgress(null)
          await loadData()
        }
      } catch {
        stopPolling()
        setRefreshing(false)
        setProgress(null)
      }
    }, 5000)
  }, [loadData])

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  // 组件卸载时清除轮询
  useEffect(() => {
    return () => stopPolling()
  }, [stopPolling])

  const triggerRefresh = useCallback(async () => {
    if (refreshing) return
    setRefreshing(true)
    setProgress(null)
    try {
      const res = await api.triggerRefresh()
      if (res.status === "already_running") {
        const st = await api.getStatus()
        if (st.progress) setProgress(st.progress)
      }
      startPolling()
    } catch {
      setRefreshing(false)
      setProgress(null)
    }
  }, [refreshing, startPolling])

  useEffect(() => {
    if (
      autoTriggered.current ||
      newsStatus !== "empty" ||
      activeDate !== todayStr() ||
      refreshing
    )
      return

    api.getStatus().then((st) => {
      if (st.pipeline_running) {
        setRefreshing(true)
        if (st.progress) setProgress(st.progress)
        startPolling()
      } else if (st.today_count === 0) {
        autoTriggered.current = true
        triggerRefresh()
      }
    })
  }, [newsStatus, activeDate, refreshing, triggerRefresh, startPolling])

  return (
    <>
      {/* 顶部导航 */}
      <header className="sticky top-0 z-30 bg-[#FAFAF9]/85 backdrop-blur-md border-b border-stone-200/80">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <SamoyedAvatar size={36} className="ring-2 ring-white shadow-sm" />
            <h1 className="text-[15px] font-bold text-[#0F0F0F] tracking-tight">Cooper 的每日新闻</h1>
          </div>
          <div className="flex items-center gap-4">
            <DateSwitcher date={activeDate} onChange={setDate} />
            <Link
              href="/favorites"
              className="text-[13px] text-[#525252] hover:text-[#0F0F0F] transition-colors flex items-center gap-1.5"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
              </svg>
              收藏
            </Link>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-10">
        {/* 标题区 */}
        <div className="mb-8 text-center">
          <span className="inline-flex items-center px-3 py-1 rounded-full bg-[#2563EB]/10 text-[#2563EB] text-[11px] font-semibold tracking-wide uppercase mb-4">
            Daily Brief
          </span>
          <h2 className="font-serif text-[40px] md:text-[52px] font-semibold text-[#0F0F0F] leading-[1.08] tracking-tight mb-3">
            今日要闻速览
          </h2>
          <p className="text-[14px] text-[#525252]">
            {formatDateZH(activeDate)} · 覆盖 10 个板块
          </p>
        </div>

        {refreshing && (
          <div className="text-center py-24">
            <div className="flex flex-col items-center gap-3">
              <span className="w-7 h-7 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin" />
              <p className="text-[#525252] text-sm">
                {progress ? progress.step : "正在为你抓取今日新闻…"}
              </p>
              {progress && (
                <div className="w-56 h-1.5 bg-stone-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#2563EB] rounded-full transition-all duration-500"
                    style={{ width: `${Math.round((progress.step_index / progress.total_steps) * 100)}%` }}
                  />
                </div>
              )}
              <p className="text-[#A3A3A3] text-xs">这通常需要 1-3 分钟，请稍候</p>
            </div>
          </div>
        )}

        {!refreshing && newsStatus === "loading" && <NewsSkeleton />}

        {!refreshing && newsStatus === "error" && (
          <div className="text-center py-24">
            <p className="text-[#525252] text-sm mb-2">加载失败</p>
            <p className="text-[#A3A3A3] text-xs">请确认后端已启动（localhost:8000）</p>
          </div>
        )}

        {!refreshing && newsStatus === "empty" && (
          <div className="text-center py-24">
            {activeDate === todayStr() ? (
              <>
                <p className="text-[#525252] text-sm mb-4">今日暂无内容</p>
                <button
                  onClick={triggerRefresh}
                  className="px-5 py-2.5 bg-[#2563EB] text-white text-sm font-medium rounded-full hover:bg-[#1D4ED8] transition-colors"
                >
                  立即抓取今日新闻
                </button>
              </>
            ) : (
              <p className="text-[#A3A3A3] text-sm">该日期暂无内容</p>
            )}
          </div>
        )}

        {newsStatus === "ok" && (
          <>
            {/* Hero */}
            {hero && (
              <div className="mb-10">
                <HeroCard
                  item={hero}
                  categories={categories}
                  onClick={() => openItem(hero)}
                  onFavoriteToggle={handleFavoriteToggle}
                />
              </div>
            )}

            {/* sticky 胶囊 tab + 搜索 */}
            <div className="sticky top-16 z-20 -mx-6 px-6 py-3 bg-[#FAFAF9]/85 backdrop-blur-md mb-8 border-b border-stone-200/60">
              {categories.length > 0 && (
                <CategoryTabs
                  categories={categories}
                  active={activeTab}
                  onChange={handleTabChange}
                  onSearch={setQuery}
                />
              )}
            </div>

            {/* 板块分区 */}
            <div className="space-y-14">
              {visibleCategories.map(({ category, items }) => (
                <SectionBlock
                  key={category.key}
                  category={category}
                  items={items}
                  categories={categories}
                  onItemClick={openItem}
                  onFavoriteToggle={handleFavoriteToggle}
                />
              ))}
              {visibleCategories.length === 0 && (
                <div className="text-center py-16">
                  <p className="text-[#A3A3A3] text-sm">没有匹配的内容</p>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <NewsDrawer
        item={selected}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onFavoriteToggle={handleFavoriteToggle}
        categories={categories}
      />
    </>
  )
}

export default function HomePage() {
  return (
    <main className="min-h-screen bg-[#FAFAF9]">
      <Suspense
        fallback={
          <div className="max-w-7xl mx-auto px-6 py-10">
            <NewsSkeleton />
          </div>
        }
      >
        <HomeContent />
      </Suspense>
    </main>
  )
}
