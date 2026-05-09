"use client"

import type { NewsItem, Category } from "@/lib/types"
import { FavoriteButton } from "./FavoriteButton"
import { gradientFor } from "./GradientCover"

interface Props {
  item: NewsItem
  categories?: Category[]
  onClick: () => void
  onFavoriteToggle?: (id: number, nowFavorited: boolean) => void
}

export function HeroCard({ item, categories, onClick, onFavoriteToggle }: Props) {
  const categoryName = categories?.find((c) => c.key === item.category)?.name ?? item.category
  const sourceName = item.source_links?.[0]?.name ?? "未知来源"
  const sourceCount = item.source_links?.length ?? 0
  const g = gradientFor(item.category)

  return (
    <article
      onClick={onClick}
      className="group relative bg-white border border-stone-200 rounded-3xl overflow-hidden cursor-pointer transition-all duration-200 hover:shadow-[0_20px_48px_rgba(15,15,15,0.08)] hover:border-stone-300"
    >
      {/* 顶部彩色细条 */}
      <span
        className="absolute top-0 left-0 right-0 h-1"
        style={{ backgroundImage: `linear-gradient(90deg, ${g.from}, ${g.via}, ${g.to})` }}
      />

      {/* 右上角装饰：超大数字 01 + 淡彩色晕 */}
      <div
        className="absolute top-0 right-0 w-64 h-64 pointer-events-none opacity-[0.08] blur-2xl"
        style={{ backgroundImage: `radial-gradient(circle, ${g.from}, transparent 70%)` }}
      />
      <span
        className="absolute top-6 right-8 text-[130px] font-black leading-none tracking-tighter pointer-events-none select-none hidden md:block"
        style={{
          fontFamily: "var(--font-geist-mono)",
          color: g.from,
          opacity: 0.08,
        }}
      >
        01
      </span>

      {/* 收藏按钮 */}
      <div
        className="absolute top-5 right-5 opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-10"
        onClick={(e) => e.stopPropagation()}
      >
        <FavoriteButton
          newsItemId={item.id}
          isFavorited={item.is_favorited}
          size="md"
          onToggle={(v) => onFavoriteToggle?.(item.id, v)}
        />
      </div>

      <div className="relative p-8 md:p-12">
        {/* 顶部徽章行 */}
        <div className="flex items-center gap-3 mb-6">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#0F0F0F] text-white text-[10.5px] font-bold tracking-[0.1em] uppercase">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#EF4444] animate-pulse" />
            今日头条
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundImage: `linear-gradient(135deg, ${g.from}, ${g.to})` }}
            />
            <span
              className="text-[11px] font-bold tracking-[0.1em] uppercase"
              style={{ color: g.from }}
            >
              {categoryName}
            </span>
          </span>
        </div>

        <h2 className="relative font-serif text-[34px] md:text-[48px] font-semibold text-[#0F0F0F] leading-[1.08] tracking-tight mb-5 md:max-w-[80%]">
          {item.title}
        </h2>

        {item.summary && (
          <p className="relative text-[16px] md:text-[17px] text-[#525252] leading-relaxed line-clamp-3 mb-8 md:max-w-[75%]">
            {item.summary}
          </p>
        )}

        <div className="flex items-center gap-3 text-[12.5px] text-[#A3A3A3]">
          <span className="font-medium text-[#525252]">{sourceName}</span>
          {sourceCount > 1 && (
            <>
              <span>·</span>
              <span>{sourceCount} 个来源</span>
            </>
          )}
          <span>·</span>
          <span>{item.date}</span>
        </div>
      </div>
    </article>
  )
}
