"use client"

import { Sheet, SheetContent } from "@/components/ui/sheet"
import type { NewsItem, Category } from "@/lib/types"
import { FavoriteButton } from "./FavoriteButton"

interface Props {
  item: NewsItem | null
  open: boolean
  onClose: () => void
  onFavoriteToggle?: (id: number, nowFavorited: boolean) => void
  categories?: Category[]
}

export function NewsDrawer({ item, open, onClose, onFavoriteToggle, categories }: Props) {
  if (!item) return null

  const categoryName = categories?.find((c) => c.key === item.category)?.name ?? item.category

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[520px] overflow-y-auto p-0 border-l border-stone-200"
      >
        {/* 顶部标题区（右上留出 40px 给 Sheet 自带的 × 按钮） */}
        <div className="px-6 pt-6 pb-4 border-b border-stone-100 pr-14">
          <div className="flex items-center gap-2 flex-wrap mb-3">
            <span className="text-xs font-medium text-[#2563EB] bg-[#2563EB]/10 px-2 py-0.5 rounded-md">
              {categoryName}
            </span>
            <span className="text-xs text-[#A3A3A3]">{item.date}</span>
            {item.source_links && item.source_links.length > 0 && (
              <span className="text-xs text-[#A3A3A3]">
                {item.source_links.length} 个来源
              </span>
            )}
          </div>
          <h2 className="font-serif text-[22px] font-semibold text-[#0F0F0F] leading-[1.25] tracking-tight mb-3">
            {item.title}
          </h2>
          <FavoriteButton
            newsItemId={item.id}
            isFavorited={item.is_favorited}
            onToggle={(v) => onFavoriteToggle?.(item.id, v)}
          />
        </div>

        {/* 内容区 */}
        <div className="px-6 py-5 space-y-6 text-sm">
          {/* 一句话摘要高亮块 */}
          {item.summary && (
            <div className="bg-stone-50 border border-stone-200 rounded-lg px-4 py-3 text-[#374151] leading-relaxed">
              {item.summary}
            </div>
          )}

          {/* 详细总结 */}
          {item.full_summary && (
            <section>
              <h3 className="text-xs font-semibold text-[#A3A3A3] uppercase tracking-wider mb-2">
                详细总结
              </h3>
              <p className="text-[#374151] leading-relaxed whitespace-pre-wrap">
                {item.full_summary}
              </p>
            </section>
          )}

          {/* 观点 */}
          {item.viewpoints && item.viewpoints.length > 0 && (
            <section>
              <h3 className="text-xs font-semibold text-[#A3A3A3] uppercase tracking-wider mb-3">
                观点
              </h3>
              <ul className="space-y-3">
                {item.viewpoints.map((vp, i) => (
                  <li key={i} className="border-l-2 border-[#2563EB]/30 pl-3">
                    <p className="text-[#374151] leading-relaxed">{vp.view}</p>
                    {vp.source && (
                      <p className="text-xs text-[#A3A3A3] mt-1">— {vp.source}</p>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 背景 */}
          {item.background && (
            <section>
              <h3 className="text-xs font-semibold text-[#A3A3A3] uppercase tracking-wider mb-2">
                背景
              </h3>
              <p className="text-[#374151] leading-relaxed whitespace-pre-wrap">
                {item.background}
              </p>
            </section>
          )}

          {/* 原文来源 */}
          {item.source_links && item.source_links.length > 0 && (
            <section>
              <h3 className="text-xs font-semibold text-[#A3A3A3] uppercase tracking-wider mb-2">
                原文来源
              </h3>
              <ul className="space-y-1.5">
                {item.source_links.map((link, i) => (
                  <li key={i}>
                    <a
                      href={link.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[#2563EB] hover:underline text-[13px] break-all"
                    >
                      {link.name || link.url}
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
