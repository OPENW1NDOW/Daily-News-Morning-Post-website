"use client"

import { useRef } from "react"

interface Props {
  date: string
  onChange: (date: string) => void
}

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

function yesterdayStr() {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return d.toISOString().slice(0, 10)
}

function formatDisplay(dateStr: string) {
  const today = todayStr()
  const yesterday = yesterdayStr()
  if (dateStr === today) return "今天"
  if (dateStr === yesterday) return "昨天"
  return dateStr
}

export function DateSwitcher({ date, onChange }: Props) {
  const today = todayStr()
  const yesterday = yesterdayStr()
  const inputRef = useRef<HTMLInputElement>(null)
  const isCustomDate = date !== today && date !== yesterday

  function openPicker() {
    const el = inputRef.current
    if (!el) return
    if (typeof el.showPicker === "function") {
      try {
        el.showPicker()
        return
      } catch {
        // 某些浏览器在非用户手势上下文下抛错，降级到 focus+click
      }
    }
    el.focus()
    el.click()
  }

  return (
    <div className="flex items-center gap-1">
      {[
        { label: "今天", value: today },
        { label: "昨天", value: yesterday },
      ].map(({ label, value }) => (
        <button
          key={value}
          onClick={() => onChange(value)}
          className={[
            "px-2.5 py-1 rounded-md text-[12px] font-medium transition-colors duration-150",
            date === value
              ? "bg-stone-100 text-[#0F0F0F]"
              : "text-[#A3A3A3] hover:text-[#525252] hover:bg-stone-50",
          ].join(" ")}
        >
          {label}
        </button>
      ))}

      <button
        type="button"
        onClick={openPicker}
        className={[
          "relative px-2.5 py-1 rounded-md text-[12px] font-medium transition-colors duration-150 flex items-center gap-1 cursor-pointer",
          isCustomDate
            ? "bg-stone-100 text-[#0F0F0F]"
            : "text-[#A3A3A3] hover:text-[#525252] hover:bg-stone-50",
        ].join(" ")}
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        {isCustomDate ? formatDisplay(date) : "历史"}

        {/* 隐藏的原生日期输入，仅作为 value 载体 + 面板锚点 */}
        <input
          ref={inputRef}
          type="date"
          value={date}
          max={today}
          onChange={(e) => e.target.value && onChange(e.target.value)}
          tabIndex={-1}
          aria-hidden="true"
          className="absolute left-0 bottom-0 w-0 h-0 opacity-0 pointer-events-none"
        />
      </button>
    </div>
  )
}
