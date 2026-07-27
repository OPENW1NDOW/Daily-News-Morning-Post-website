"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { api } from "@/lib/api"
import { todayStr } from "@/lib/utils"
import { isAuthenticated, clearToken } from "@/lib/auth"
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

function isValidDateStr(s: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(s) && !Number.isNaN(new Date(`${s}T00:00:00`).getTime())
}

export function HomeContent() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [categories, setCategories] = useState<Category[]>([])
  const [itemsByCategory, setItemsByCategory] = useState<Record<string, NewsItem[]>>({})
  const [failedCategories, setFailedCategories] = useState<string[]>([])
  const [newsStatus, setNewsStatus] = useState<"loading" | "ok" | "empty" | "error">("loading")
  const [refreshing, setRefreshing] = useState(false)
  const [pollError, setPollError] = useState(false)
  const [progress, setProgress] = useState<PipelineProgress | null>(null)
  const [activeTab, setActiveTab] = useState<string>("all")
  const [query, setQuery] = useState("")
  const [user, setUser] = useState<{ id: number; username: string; is_admin?: boolean } | null>(null)
  const autoTriggered = useRef(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const seqRef = useRef(0)
  const refreshingRef = useRef(false)
  const pollFailRef = useRef(0)

  // 检查登录状态
  useEffect(() => {
    if (isAuthenticated()) {
      api.getMe().then(setUser).catch(() => { clearToken(); setUser(null) })
    }
  }, [])

  const rawDate = searchParams.get("date")
  const activeDate = rawDate && isValidDateStr(rawDate) ? rawDate : todayStr()

  function setDate(d: string) {
    const p = new URLSearchParams(searchParams.toString())
    p.set("date", d)
    p.delete("item")
    router.replace(`/?${p}`, { scroll: false })
  }

  const setRefreshingState = useCallback((v: boolean) => {
    refreshingRef.current = v
    setRefreshing(v)
  }, [])

  const loadData = useCallback(async () => {
    // 请求序号守卫：快速切换日期时，旧响应不得覆盖新数据
    const seq = ++seqRef.current
    if (!refreshingRef.current) setNewsStatus("loading")
    try {
      const cats = await api.getCategories(activeDate)
      if (seq !== seqRef.current) return
      setCategories(cats)

      const results = await Promise.allSettled(
        cats.map((c) =>
          api.getNews({ category: c.key, date: activeDate }).then((items) => [c.key, items] as const)
        )
      )
      if (seq !== seqRef.current) return

      const map: Record<string, NewsItem[]> = {}
      const failed: string[] = []
      let total = 0
      results.forEach((r, i) => {
        if (r.status === "fulfilled") {
          const [key, items] = r.value
          map[key] = items
          total += items.length
        } else {
          failed.push(cats[i].key)
        }
      })
      setItemsByCategory(map)
      setFailedCategories(failed)
      if (cats.length > 0 && failed.length === cats.length) {
        setNewsStatus("error")
      } else if (total === 0 && failed.length === 0) {
        setNewsStatus("empty")
      } else {
        setNewsStatus("ok")
      }
    } catch {
      if (seq === seqRef.current) setNewsStatus("error")
    }
  }, [activeDate])

  const loadDataRef = useRef(loadData)
  useEffect(() => {
    loadDataRef.current = loadData
  }, [loadData])

  useEffect(() => {
    loadData()
  }, [loadData])

  const retryCategory = useCallback(async (key: string) => {
    const seq = seqRef.current
    try {
      const items = await api.getNews({ category: key, date: activeDate })
      if (seq !== seqRef.current) return
      setItemsByCategory((prev) => ({ ...prev, [key]: items }))
      setFailedCategories((prev) => prev.filter((k) => k !== key))
    } catch {
      // 重试仍失败：维持失败标记，用户可再次重试
    }
  }, [activeDate])

  // 详情弹窗：由 URL 的 ?item= 派生，单一事实源
  const itemParam = searchParams.get("item")
  const selectedItem = useMemo(() => {
    if (!itemParam) return null
    const id = Number(itemParam)
    if (!Number.isInteger(id)) return null
    for (const list of Object.values(itemsByCategory)) {
      const found = list.find((it) => it.id === id)
      if (found) return found
    }
    return null
  }, [itemParam, itemsByCategory])

  function openItem(item: NewsItem) {
    const p = new URLSearchParams(searchParams.toString())
    p.set("item", String(item.id))
    // push 而非 replace：手机返回键可直接关闭弹窗
    router.push(`/?${p}`, { scroll: false })
  }

  const closeItem = useCallback(() => {
    const p = new URLSearchParams(searchParams.toString())
    p.delete("item")
    const qs = p.toString()
    router.replace(qs ? `/?${qs}` : "/", { scroll: false })
  }, [router, searchParams])

  // 数据加载完成后，URL 里的 item 找不到对应条目则静默清掉
  useEffect(() => {
    if (!itemParam) return
    if (newsStatus !== "ok" && newsStatus !== "empty") return
    if (!selectedItem) closeItem()
  }, [itemParam, newsStatus, selectedItem, closeItem])

  // Hero：全天 importance 最高的 1 条（排除 following）
  const { hero, sectionItems } = useMemo(() => {
    const all = Object.values(itemsByCategory).flat()
    if (all.length === 0) return { hero: null as NewsItem | null, sectionItems: {} as Record<string, NewsItem[]> }
    const candidates = all.filter((it) => it.category !== "following")
    const hero = candidates.length
      ? candidates.reduce((a, b) => (b.importance > a.importance ? b : a))
      : null
    const sectionItems: Record<string, NewsItem[]> = {}
    for (const [key, items] of Object.entries(itemsByCategory)) {
      sectionItems[key] = hero ? items.filter((it) => it.id !== hero.id) : items
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

  const visibleFailed = useMemo(
    () => failedCategories.filter((k) => activeTab === "all" || k === activeTab),
    [failedCategories, activeTab]
  )

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

  function handleFavoriteToggle(id: number, nowFavorited: boolean) {
    setItemsByCategory((prev) => {
      const next: Record<string, NewsItem[]> = {}
      for (const [k, list] of Object.entries(prev)) {
        next[k] = list.map((it) => (it.id === id ? { ...it, is_favorited: nowFavorited } : it))
      }
      return next
    })
  }

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  // 统一轮询逻辑
  const startPolling = useCallback(() => {
    if (pollRef.current) return
    pollFailRef.current = 0
    pollRef.current = setInterval(async () => {
      try {
        const st = await api.getStatus()
        pollFailRef.current = 0
        if (st.progress) setProgress(st.progress)
        if (!st.pipeline_running) {
          stopPolling()
          await loadDataRef.current()
          setRefreshingState(false)
          setProgress(null)
        }
      } catch {
        // 偶发网络抖动不打断等待，连续 3 次失败才停止
        pollFailRef.current += 1
        if (pollFailRef.current >= 3) {
          stopPolling()
          setRefreshingState(false)
          setProgress(null)
          setPollError(true)
        }
      }
    }, 5000)
  }, [stopPolling, setRefreshingState])

  // 组件卸载时清除轮询
  useEffect(() => {
    return () => stopPolling()
  }, [stopPolling])

  const retryStatus = useCallback(async () => {
    setPollError(false)
    setRefreshingState(true)
    try {
      const st = await api.getStatus()
      if (st.pipeline_running) {
        if (st.progress) setProgress(st.progress)
        startPolling()
      } else {
        await loadDataRef.current()
        setRefreshingState(false)
        setProgress(null)
      }
    } catch {
      setRefreshingState(false)
      setPollError(true)
    }
  }, [setRefreshingState, startPolling])

  const triggerRefresh = useCallback(async () => {
    if (refreshingRef.current) return
    setPollError(false)
    setRefreshingState(true)
    setProgress(null)
    try {
      const res = await api.triggerRefresh()
      if (res.status === "already_running") {
        const st = await api.getStatus()
        if (st.progress) setProgress(st.progress)
      }
      startPolling()
    } catch {
      setRefreshingState(false)
      setProgress(null)
    }
  }, [setRefreshingState, startPolling])

  useEffect(() => {
    if (
      autoTriggered.current ||
      newsStatus !== "empty" ||
      activeDate !== todayStr() ||
      refreshing ||
      pollError
    )
      return

    api.getStatus().then((st) => {
      if (st.pipeline_running) {
        setRefreshingState(true)
        if (st.progress) setProgress(st.progress)
        startPolling()
      } else if (st.today_count === 0) {
        autoTriggered.current = true
        triggerRefresh()
      }
    }).catch(() => {})
  }, [newsStatus, activeDate, refreshing, pollError, triggerRefresh, startPolling, setRefreshingState])

  // 进度：步骤基线 + 板块完成度插值，避免长时间停在同一格
  const progressPct = useMemo(() => {
    if (!progress || progress.total_steps <= 0) return 0
    const stepBase = Math.max(0, progress.step_index - 1) / progress.total_steps
    const catFrac =
      progress.total_categories > 0
        ? progress.categories_done / progress.total_categories / progress.total_steps
        : 0
    return Math.min(100, Math.round((stepBase + catFrac) * 100))
  }, [progress])

  return (
    <>
      {/* 顶部导航 */}
      <header className="sticky top-0 z-30 bg-[#FAFAF9]/85 backdrop-blur-md border-b border-stone-200/80">
        <div className="max-w-7xl mx-auto px-4 md:px-6 h-16 flex items-center justify-between gap-2 md:gap-4">
          <div className="flex items-center gap-2.5 min-w-0">
            <SamoyedAvatar size={36} className="ring-2 ring-white shadow-sm shrink-0" />
            <h1 className="hidden sm:block text-[15px] font-bold text-[#0F0F0F] tracking-tight truncate">Cooper 的每日新闻</h1>
          </div>
          <div className="flex items-center gap-2 md:gap-4">
            <DateSwitcher date={activeDate} onChange={setDate} />
            <Link
              href="/favorites"
              aria-label="收藏"
              className="text-[13px] text-[#525252] hover:text-[#0F0F0F] transition-colors flex items-center gap-1.5"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
              </svg>
              <span className="hidden md:inline">收藏</span>
            </Link>
            {user?.is_admin && (
              <Link
                href="/admin"
                aria-label="管理"
                className="text-[13px] text-[#525252] hover:text-[#0F0F0F] transition-colors flex items-center gap-1.5"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <span className="hidden md:inline">管理</span>
              </Link>
            )}
            {user ? (
              <div className="flex items-center gap-2">
                <span className="hidden md:inline text-[13px] text-[#525252]">{user.username}</span>
                <button
                  onClick={() => { clearToken(); setUser(null); router.refresh() }}
                  aria-label="退出登录"
                  className="text-[13px] text-[#737373] hover:text-[#0F0F0F] flex items-center gap-1.5"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                  <span className="hidden md:inline">退出</span>
                </button>
              </div>
            ) : (
              <Link href="/login" className="text-[13px] text-[#2563EB] hover:underline">
                登录
              </Link>
            )}
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-10">
        {/* 报头 masthead */}
        <div className="mb-8 border-t-2 border-[#0F0F0F] pt-3">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2 className="font-serif text-xl font-semibold text-[#0F0F0F] tracking-tight">今日要闻速览</h2>
            <p className="text-sm text-[#737373]">
              {formatDateZH(activeDate)}
              {categories.length > 0 ? ` · ${categories.length} 个板块` : ""}
            </p>
          </div>
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
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
              )}
              <p className="text-[#737373] text-xs">
                {progress && progress.total_categories > 0 && progress.categories_done > 0
                  ? `板块进度 ${progress.categories_done}/${progress.total_categories}`
                  : "这通常需要 1-3 分钟，请稍候"}
              </p>
            </div>
          </div>
        )}

        {!refreshing && pollError && (
          <div className="text-center py-24">
            <p className="text-[#525252] text-sm mb-2">状态获取失败</p>
            <p className="text-[#737373] text-xs mb-5">网络似乎不太稳定，稍后可以再试一次</p>
            <button
              onClick={retryStatus}
              className="px-5 py-2.5 bg-[#2563EB] text-white text-sm font-medium rounded-full hover:bg-[#1D4ED8] transition-colors"
            >
              重试
            </button>
          </div>
        )}

        {!refreshing && !pollError && newsStatus === "loading" && <NewsSkeleton />}

        {!refreshing && !pollError && newsStatus === "error" && (
          <div className="text-center py-24">
            <p className="text-[#525252] text-sm mb-2">内容加载失败</p>
            <p className="text-[#737373] text-xs mb-5">网络或服务暂时不可用，请稍后重试</p>
            <button
              onClick={() => loadData()}
              className="px-5 py-2.5 bg-[#2563EB] text-white text-sm font-medium rounded-full hover:bg-[#1D4ED8] transition-colors"
            >
              重新加载
            </button>
          </div>
        )}

        {!refreshing && !pollError && newsStatus === "empty" && (
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
              <p className="text-[#737373] text-sm">该日期暂无内容</p>
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

              {/* 加载失败的板块：局部错误提示 + 单板块重试 */}
              {visibleFailed.map((key) => {
                const cat = categories.find((c) => c.key === key)
                return (
                  <div
                    key={key}
                    id={`cat-${key}`}
                    className="rounded-xl border border-stone-200 bg-white px-6 py-8 text-center scroll-mt-24"
                  >
                    <p className="text-[#525252] text-sm mb-3">
                      「{cat?.name ?? key}」板块加载失败
                    </p>
                    <button
                      onClick={() => retryCategory(key)}
                      className="px-4 py-2 text-[13px] font-medium text-[#2563EB] border border-[#2563EB]/30 rounded-full hover:bg-[#2563EB]/5 transition-colors"
                    >
                      重试该板块
                    </button>
                  </div>
                )
              })}

              {visibleCategories.length === 0 && visibleFailed.length === 0 && (
                <div className="text-center py-16">
                  <p className="text-[#737373] text-sm">没有匹配的内容</p>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <NewsDrawer
        item={selectedItem}
        open={selectedItem !== null}
        onClose={closeItem}
        onFavoriteToggle={handleFavoriteToggle}
        categories={categories}
      />
    </>
  )
}
