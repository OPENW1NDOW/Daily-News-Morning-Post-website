"use client"

import type { NewsItem, Category } from "@/lib/types"
import { NewsCard } from "./NewsCard"
import { gradientFor } from "./GradientCover"

interface Props {
  category: Category
  items: NewsItem[]
  categories: Category[]
  onItemClick: (item: NewsItem) => void
  onFavoriteToggle?: (id: number, nowFavorited: boolean) => void
}

export function SectionBlock({ category, items, categories, onItemClick, onFavoriteToggle }: Props) {
  if (items.length === 0) return null

  const g = gradientFor(category.key)

  return (
    <section id={`cat-${category.key}`} className="scroll-mt-24">
      <div className="flex items-end justify-between gap-4 mb-5 pb-3 border-b border-stone-200">
        <div className="flex items-center gap-3">
          <span
            className="inline-block w-2.5 h-2.5 rounded-full"
            style={{ backgroundImage: `linear-gradient(135deg, ${g.from}, ${g.to})` }}
          />
          <h2 className="font-serif text-[24px] font-semibold text-[#0F0F0F] tracking-tight">
            {category.name}
          </h2>
          {category.description && (
            <span className="text-[13px] text-[#A3A3A3] hidden md:inline">
              {category.description}
            </span>
          )}
        </div>
        <span className="text-[12px] text-[#A3A3A3] shrink-0">共 {items.length} 条</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {items.map((item) => (
          <NewsCard
            key={item.id}
            item={item}
            categories={categories}
            onClick={() => onItemClick(item)}
            onFavoriteToggle={onFavoriteToggle}
          />
        ))}
      </div>
    </section>
  )
}
