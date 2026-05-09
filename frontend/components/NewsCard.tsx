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

export function NewsCard({ item, categories, onClick, onFavoriteToggle }: Props) {
  const sourceName = item.source_links?.[0]?.name ?? "未知来源"
  const categoryName = categories?.find((c) => c.key === item.category)?.name ?? item.category
  const g = gradientFor(item.category)
  const isImportant = item.importance >= 70

  return (
    <article
      onClick={onClick}
      className="group relative flex flex-col bg-white border border-stone-200 rounded-2xl p-6 cursor-pointer transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_12px_28px_rgba(15,15,15,0.06)] hover:border-stone-300 overflow-hidden"
    >
      {/* 左侧细彩条 */}
      <span
        className="absolute left-0 top-0 bottom-0 w-1"
        style={{ backgroundImage: `linear-gradient(180deg, ${g.from}, ${g.to})` }}
      />

      {/* 收藏按钮 */}
      <div
        className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        <FavoriteButton
          newsItemId={item.id}
          isFavorited={item.is_favorited}
          size="sm"
          onToggle={(v) => onFavoriteToggle?.(item.id, v)}
        />
      </div>

      {/* 板块徽章 */}
      <div className="flex items-center gap-1.5 mb-3">
        <span
          className="inline-block w-1.5 h-1.5 rounded-full"
          style={{ backgroundImage: `linear-gradient(135deg, ${g.from}, ${g.to})` }}
        />
        <span
          className="text-[10.5px] font-bold tracking-[0.08em] uppercase"
          style={{ color: g.from }}
        >
          {categoryName}
        </span>
        {isImportant && (
          <span className="text-[10px] text-[#A3A3A3] font-medium">· 重要</span>
        )}
      </div>

      <h3 className="text-[17px] font-bold text-[#0F0F0F] leading-[1.35] tracking-tight line-clamp-2 mb-2.5 pr-6">
        {item.title}
      </h3>

      {item.summary && (
        <p className="text-[13px] text-[#525252] leading-relaxed line-clamp-3 mb-4">
          {item.summary}
        </p>
      )}

      <div className="flex items-center gap-2 pt-3 mt-auto border-t border-stone-100 text-[11.5px] text-[#A3A3A3]">
        <span className="truncate">{sourceName}</span>
        {item.source_links && item.source_links.length > 1 && (
          <span className="text-[11px] text-[#C0BDBA] shrink-0">· +{item.source_links.length - 1}</span>
        )}
      </div>
    </article>
  )
}
