"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { api } from "@/lib/api"
import type { NewsItem, Category } from "@/lib/types"
import { NewsCard } from "@/components/NewsCard"
import { NewsDrawer } from "@/components/NewsDrawer"
import { NewsSkeleton } from "@/components/NewsSkeleton"
import { SamoyedAvatar } from "@/components/SamoyedAvatar"
import { gradientFor } from "@/components/GradientCover"

export default function FavoritesPage() {
  const [items, setItems] = useState<NewsItem[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [status, setStatus] = useState<"loading" | "ok" | "empty" | "error">("loading")
  const [selected, setSelected] = useState<NewsItem | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [activeFilter, setActiveFilter] = useState<string>("all")

  function load(p: number) {
    setStatus("loading")
    Promise.all([api.getFavorites(p), api.getCategories()])
      .then(([data, cats]) => {
        setItems(data.items)
        setTotalPages(data.pages)
        setTotal(data.total)
        setCategories(cats)
        setStatus(data.items.length === 0 ? "empty" : "ok")
      })
      .catch(() => setStatus("error"))
  }

  useEffect(() => { load(page) }, [page])

  function handleFavoriteToggle(id: number, nowFavorited: boolean) {
    if (!nowFavorited) {
      setItems((prev) => prev.filter((it) => it.id !== id))
      setTotal((t) => Math.max(0, t - 1))
      if (selected?.id === id) setDrawerOpen(false)
    }
  }

  const filterOptions = useMemo(() => {
    const counts = new Map<string, number>()
    for (const it of items) counts.set(it.category, (counts.get(it.category) ?? 0) + 1)
    const present = categories
      .filter((c) => counts.get(c.key))
      .map((c) => ({ key: c.key, name: c.name, count: counts.get(c.key)! }))
    return [{ key: "all", name: "全部", count: items.length }, ...present]
  }, [items, categories])

  const groups = useMemo(() => {
    const filtered = activeFilter === "all" ? items : items.filter((it) => it.category === activeFilter)
    const map = new Map<string, NewsItem[]>()
    for (const it of filtered) {
      if (!map.has(it.category)) map.set(it.category, [])
      map.get(it.category)!.push(it)
    }
    return categories
      .filter((c) => map.has(c.key))
      .map((c) => ({ category: c, items: map.get(c.key)! }))
  }, [items, activeFilter, categories])

  return (
    <main className="min-h-screen bg-[#FAFAF9]">
      {/* 顶部导航（与首页一致） */}
      <header className="sticky top-0 z-30 bg-[#FAFAF9]/85 backdrop-blur-md border-b border-stone-200/80">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-2.5 group">
            <SamoyedAvatar size={36} className="ring-2 ring-white shadow-sm" />
            <h1 className="text-[15px] font-bold text-[#0F0F0F] tracking-tight group-hover:opacity-70 transition-opacity">
              Cooper 的每日新闻
            </h1>
          </Link>
          <Link
            href="/"
            className="text-[13px] text-[#525252] hover:text-[#0F0F0F] transition-colors flex items-center gap-1.5"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            返回首页
          </Link>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-10">
        {/* 标题区 */}
        <div className="mb-8 text-center">
          <span className="inline-flex items-center px-3 py-1 rounded-full bg-[#2563EB]/10 text-[#2563EB] text-[11px] font-semibold tracking-wide uppercase mb-4">
            My Collection
          </span>
          <h2 className="font-serif text-[40px] md:text-[52px] font-semibold text-[#0F0F0F] leading-[1.08] tracking-tight mb-3">
            我的收藏
          </h2>
          <p className="text-[14px] text-[#525252]">
            {status === "ok" || status === "empty"
              ? total > 0
                ? `已收藏 ${total} 条 · 跨 ${filterOptions.length - 1} 个板块`
                : "还没有收藏任何内容"
              : "加载中…"}
          </p>
        </div>

        {status === "loading" && <NewsSkeleton />}

        {status === "error" && (
          <div className="text-center py-24">
            <p className="text-[#525252] text-sm mb-2">加载失败</p>
            <p className="text-[#A3A3A3] text-xs">请确认后端已启动（localhost:8000）</p>
          </div>
        )}

        {status === "empty" && (
          <div className="text-center py-24">
            <div className="relative inline-block mb-6">
              <SamoyedAvatar
                size={112}
                className="ring-4 ring-white shadow-[0_8px_32px_rgba(15,15,15,0.10)]"
              />
              <span className="absolute -top-1 -right-1 inline-flex items-center justify-center w-9 h-9 rounded-full bg-white border border-stone-200 shadow-sm">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-[#A3A3A3]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
                </svg>
              </span>
            </div>
            <h3 className="text-[18px] font-bold text-[#0F0F0F] mb-1.5">收藏夹空空的</h3>
            <p className="text-[#A3A3A3] text-[13px] mb-6">点击卡片右上角的书签，把喜欢的新闻留下来</p>
            <Link
              href="/"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#2563EB] text-white text-sm font-medium rounded-full hover:bg-[#1D4ED8] transition-colors"
            >
              去看今日新闻
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 8l4 4m0 0l-4 4m4-4H3" />
              </svg>
            </Link>
          </div>
        )}

        {status === "ok" && (
          <>
            {/* 板块筛选胶囊 */}
            {filterOptions.length > 2 && (
              <div className="sticky top-16 z-20 -mx-6 px-6 py-3 bg-[#FAFAF9]/85 backdrop-blur-md mb-8 border-b border-stone-200/60">
                <div className="flex gap-1.5 overflow-x-auto scrollbar-none py-1">
                  {filterOptions.map((opt) => {
                    const isActive = opt.key === activeFilter
                    return (
                      <button
                        key={opt.key}
                        onClick={() => setActiveFilter(opt.key)}
                        className={[
                          "shrink-0 px-3.5 py-1.5 rounded-full text-[13px] font-medium transition-all duration-150 whitespace-nowrap",
                          isActive
                            ? "bg-[#0F0F0F] text-white shadow-sm"
                            : "bg-white text-[#525252] border border-stone-200 hover:border-stone-300 hover:text-[#0F0F0F]",
                        ].join(" ")}
                      >
                        {opt.name}
                        <span className={`ml-1.5 text-[11px] ${isActive ? "opacity-70" : "text-[#A3A3A3]"}`}>
                          {opt.count}
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {/* 板块分组网格 */}
            <div className="space-y-14">
              {groups.map(({ category, items: groupItems }) => {
                const g = gradientFor(category.key)
                return (
                  <section key={category.key} id={`cat-${category.key}`} className="scroll-mt-24">
                    <div className="flex items-end justify-between gap-4 mb-5 pb-3 border-b border-stone-200">
                      <div className="flex items-center gap-3">
                        <span
                          className="inline-block w-2.5 h-2.5 rounded-full"
                          style={{ backgroundImage: `linear-gradient(135deg, ${g.from}, ${g.to})` }}
                        />
                        <h2 className="font-serif text-[24px] font-semibold text-[#0F0F0F] tracking-tight">
                          {category.name}
                        </h2>
                      </div>
                      <span className="text-[12px] text-[#A3A3A3] shrink-0">
                        {groupItems.length} 条收藏
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                      {groupItems.map((item) => (
                        <NewsCard
                          key={item.id}
                          item={item}
                          categories={categories}
                          onClick={() => { setSelected(item); setDrawerOpen(true) }}
                          onFavoriteToggle={handleFavoriteToggle}
                        />
                      ))}
                    </div>
                  </section>
                )
              })}

              {groups.length === 0 && (
                <div className="text-center py-16">
                  <p className="text-[#A3A3A3] text-sm">该板块暂无收藏</p>
                </div>
              )}
            </div>

            {/* 分页 */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-4 mt-14">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="w-10 h-10 rounded-full border border-stone-200 bg-white text-[#525252] hover:text-[#0F0F0F] hover:border-stone-400 transition-all disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center"
                  aria-label="上一页"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} className="w-4 h-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                  </svg>
                </button>
                <span className="text-[13px] text-[#525252] tabular-nums">
                  {page} <span className="text-[#A3A3A3]">/ {totalPages}</span>
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="w-10 h-10 rounded-full border border-stone-200 bg-white text-[#525252] hover:text-[#0F0F0F] hover:border-stone-400 transition-all disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center"
                  aria-label="下一页"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} className="w-4 h-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <NewsDrawer
        item={selected}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onFavoriteToggle={handleFavoriteToggle}
      />
    </main>
  )
}
