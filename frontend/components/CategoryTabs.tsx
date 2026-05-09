"use client"

import { useEffect, useRef, useState } from "react"
import type { Category } from "@/lib/types"

interface Props {
  categories: Category[]
  active: string
  onChange: (key: string) => void
  onSearch?: (q: string) => void
}

export function CategoryTabs({ categories, active, onChange, onSearch }: Props) {
  const [q, setQ] = useState("")
  const scrollRef = useRef<HTMLDivElement>(null)
  const [atStart, setAtStart] = useState(true)
  const [atEnd, setAtEnd] = useState(false)

  function updateEdges() {
    const el = scrollRef.current
    if (!el) return
    setAtStart(el.scrollLeft <= 2)
    setAtEnd(el.scrollLeft + el.clientWidth >= el.scrollWidth - 2)
  }

  useEffect(() => {
    updateEdges()
    const el = scrollRef.current
    if (!el) return
    el.addEventListener("scroll", updateEdges, { passive: true })
    window.addEventListener("resize", updateEdges)
    return () => {
      el.removeEventListener("scroll", updateEdges)
      window.removeEventListener("resize", updateEdges)
    }
  }, [categories.length])

  // 激活 tab 自动滚动到可见区
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const btn = el.querySelector<HTMLButtonElement>(`[data-key="${active}"]`)
    btn?.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" })
  }, [active])

  function scrollBy(delta: number) {
    scrollRef.current?.scrollBy({ left: delta, behavior: "smooth" })
  }

  return (
    <div className="flex items-center gap-3">
      {/* 左箭头 */}
      <button
        type="button"
        aria-label="向左滚动"
        onClick={() => scrollBy(-240)}
        className={`shrink-0 w-8 h-8 rounded-full border border-stone-200 bg-white text-[#525252] hover:text-[#0F0F0F] hover:border-stone-400 transition-all duration-150 flex items-center justify-center ${
          atStart ? "opacity-0 pointer-events-none" : "opacity-100"
        }`}
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} className="w-4 h-4">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
      </button>

      {/* tab 列表 + 左右渐隐遮罩 */}
      <div className="relative flex-1 min-w-0">
        <div
          ref={scrollRef}
          className="flex gap-1.5 overflow-x-auto scrollbar-none py-1 -mx-1 px-1 scroll-smooth"
        >
          <button
            data-key="all"
            onClick={() => onChange("all")}
            className={tabClass(active === "all")}
          >
            全部
          </button>
          {categories.map((cat) => {
            const isActive = cat.key === active
            return (
              <button
                key={cat.key}
                data-key={cat.key}
                onClick={() => onChange(cat.key)}
                className={tabClass(isActive)}
              >
                {cat.name}
                {cat.count > 0 && (
                  <span className={`ml-1.5 text-[11px] ${isActive ? "opacity-70" : "text-[#A3A3A3]"}`}>
                    {cat.count}
                  </span>
                )}
              </button>
            )
          })}
        </div>

        {/* 左右渐隐遮罩 */}
        <div
          className={`pointer-events-none absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-[#FAFAF9] to-transparent transition-opacity ${
            atStart ? "opacity-0" : "opacity-100"
          }`}
        />
        <div
          className={`pointer-events-none absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-[#FAFAF9] to-transparent transition-opacity ${
            atEnd ? "opacity-0" : "opacity-100"
          }`}
        />
      </div>

      {/* 右箭头 */}
      <button
        type="button"
        aria-label="向右滚动"
        onClick={() => scrollBy(240)}
        className={`shrink-0 w-8 h-8 rounded-full border border-stone-200 bg-white text-[#525252] hover:text-[#0F0F0F] hover:border-stone-400 transition-all duration-150 flex items-center justify-center ${
          atEnd ? "opacity-0 pointer-events-none" : "opacity-100"
        }`}
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} className="w-4 h-4">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </button>

      {/* 搜索框 */}
      <div className="shrink-0 hidden md:flex items-center gap-2 px-3 h-9 bg-white border border-stone-200 rounded-full focus-within:border-stone-400 transition-colors">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4 text-[#A3A3A3]">
          <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-4.35-4.35M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15Z" />
        </svg>
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            onSearch?.(e.target.value)
          }}
          placeholder="搜索…"
          className="bg-transparent outline-none text-[13px] text-[#0F0F0F] placeholder:text-[#A3A3A3] w-36"
        />
      </div>
    </div>
  )
}

function tabClass(active: boolean) {
  return [
    "shrink-0 px-3.5 py-1.5 rounded-full text-[13px] font-medium transition-all duration-150 whitespace-nowrap",
    active
      ? "bg-[#0F0F0F] text-white shadow-sm"
      : "bg-white text-[#525252] border border-stone-200 hover:border-stone-300 hover:text-[#0F0F0F]",
  ].join(" ")
}
