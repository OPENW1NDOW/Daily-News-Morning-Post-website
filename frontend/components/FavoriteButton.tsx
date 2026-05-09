"use client"

import { useState, useEffect } from "react"
import { api } from "@/lib/api"

interface Props {
  newsItemId: number
  isFavorited: boolean
  onToggle?: (nowFavorited: boolean) => void
  size?: "sm" | "md"
}

export function FavoriteButton({ newsItemId, isFavorited, onToggle, size = "md" }: Props) {
  const [optimistic, setOptimistic] = useState(isFavorited)
  const [busy, setBusy] = useState(false)

  useEffect(() => { setOptimistic(isFavorited) }, [isFavorited])

  async function toggle(e: React.MouseEvent) {
    e.stopPropagation()
    if (busy) return
    setBusy(true)
    const next = !optimistic
    setOptimistic(next)
    try {
      if (next) {
        await api.addFavorite(newsItemId)
      } else {
        await api.removeFavorite(newsItemId)
      }
      onToggle?.(next)
    } catch {
      setOptimistic(!next)
    } finally {
      setBusy(false)
    }
  }

  const sizeClass = size === "sm" ? "w-7 h-7" : "w-8 h-8"

  return (
    <button
      onClick={toggle}
      aria-label={optimistic ? "取消收藏" : "收藏"}
      className={[
        sizeClass,
        "flex items-center justify-center rounded-full transition-all duration-150",
        optimistic
          ? "text-[#1E3A5F] bg-blue-50 hover:bg-blue-100"
          : "text-[#A3A3A3] hover:text-[#1E3A5F] hover:bg-blue-50",
      ].join(" ")}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill={optimistic ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth={2}
        className={size === "sm" ? "w-3.5 h-3.5" : "w-4 h-4"}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z"
        />
      </svg>
    </button>
  )
}
