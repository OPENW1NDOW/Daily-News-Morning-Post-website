import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** 与后端 business_date 一致：Asia/Shanghai，08:00 前算前一天 */
export function todayStr(now = new Date()) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    hourCycle: "h23",
  }).formatToParts(now)
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? "0")
  let y = get("year")
  let m = get("month")
  let d = get("day")
  const hour = get("hour")
  if (hour < 8) {
    const dt = new Date(Date.UTC(y, m - 1, d))
    dt.setUTCDate(dt.getUTCDate() - 1)
    y = dt.getUTCFullYear()
    m = dt.getUTCMonth() + 1
    d = dt.getUTCDate()
  }
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`
}

/** 后端时间统一转 Asia/Shanghai 展示：naive 字符串按 UTC 解释（补 Z），已带时区标记的原样解析 */
export function formatDateTime(iso: string): string {
  const hasTimezone = /(Z|[+-]\d{2}:?\d{2})$/.test(iso)
  const d = new Date(hasTimezone ? iso : iso + "Z")
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false })
}

export function yesterdayStr() {
  const [y, m, d] = todayStr().split("-").map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d))
  dt.setUTCDate(dt.getUTCDate() - 1)
  return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, "0")}-${String(dt.getUTCDate()).padStart(2, "0")}`
}
