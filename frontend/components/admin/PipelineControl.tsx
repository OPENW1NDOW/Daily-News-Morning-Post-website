"use client"

import { useEffect, useRef, useState, useCallback } from "react"
import { api } from "@/lib/api"
import type { PipelineProgress, PipelineRun } from "@/lib/types"
import { formatDateTime } from "@/lib/utils"
import { Play, Loader2, CheckCircle2, XCircle, Clock } from "lucide-react"

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  success: { label: "成功", color: "text-green-600 bg-green-50" },
  error: { label: "失败", color: "text-red-600 bg-red-50" },
  running: { label: "运行中", color: "text-blue-600 bg-blue-50" },
}

export default function PipelineControl() {
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState<PipelineProgress | null>(null)
  const [history, setHistory] = useState<PipelineRun[]>([])
  const [historyPage, setHistoryPage] = useState(1)
  const [historyPages, setHistoryPages] = useState(1)
  const [triggering, setTriggering] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadHistory = useCallback((page = 1) => {
    api.adminPipelineHistory(page).then((res) => {
      setHistory(res.items)
      setHistoryPage(res.page)
      setHistoryPages(res.pages)
    })
  }, [])

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  const startPolling = useCallback(() => {
    stopPolling()
    intervalRef.current = setInterval(async () => {
      try {
        const st = await api.adminPipelineStatus()
        if (st.progress) setProgress(st.progress)
        if (!st.pipeline_running) {
          setRunning(false)
          setProgress(null)
          stopPolling()
          loadHistory()
        }
      } catch {
        stopPolling()
        setRunning(false)
      }
    }, 3000)
  }, [stopPolling, loadHistory])

  useEffect(() => {
    // 初始检查流水线状态
    api.adminPipelineStatus().then((st) => {
      setRunning(st.pipeline_running)
      if (st.pipeline_running && st.progress) {
        setProgress(st.progress)
        startPolling()
      }
    })
    loadHistory()
    return () => stopPolling()
  }, [startPolling, stopPolling, loadHistory])

  const handleTrigger = async () => {
    if (triggering || running) return
    setTriggering(true)
    try {
      const res = await api.adminTriggerPipeline()
      if (res.status === "started" || res.status === "already_running") {
        setRunning(true)
        startPolling()
      }
    } finally {
      setTriggering(false)
    }
  }

  const progressPct = progress ? Math.round((progress.step_index / progress.total_steps) * 100) : 0

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-[#0F0F0F]">流水线控制</h2>

      {/* 触发区域 */}
      <div className="bg-white rounded-xl border border-[#E5E5E5] p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-medium text-[#0F0F0F]">手动触发</h3>
            <p className="text-[13px] text-[#737373] mt-0.5">执行完整的新闻采集-分类-摘要流水线</p>
          </div>
          <button
            onClick={handleTrigger}
            disabled={running || triggering}
            className="flex items-center gap-2 px-4 py-2 bg-[#2563EB] text-white text-[13px] rounded-lg hover:bg-[#1D4ED8] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            {running ? "运行中..." : triggering ? "启动中..." : "立即执行"}
          </button>
        </div>

        {/* 进度条 */}
        {running && progress && (
          <div className="mt-4 space-y-2">
            <div className="flex justify-between text-[13px]">
              <span className="text-[#525252]">{progress.step}</span>
              <span className="text-[#737373]">{progressPct}%</span>
            </div>
            <div className="w-full h-2 bg-[#F5F5F4] rounded-full overflow-hidden">
              <div className="h-full bg-[#2563EB] rounded-full transition-all duration-500" style={{ width: `${progressPct}%` }} />
            </div>
            <p className="text-[12px] text-[#A3A3A3]">
              步骤 {progress.step_index}/{progress.total_steps} · 板块进度 {progress.categories_done}/{progress.total_categories}
            </p>
          </div>
        )}
      </div>

      {/* 运行历史 */}
      <div className="bg-white rounded-xl border border-[#E5E5E5] p-5">
        <h3 className="text-sm font-medium text-[#0F0F0F] mb-4">运行历史</h3>
        {history.length === 0 ? (
          <p className="text-[13px] text-[#A3A3A3]">暂无运行记录</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-[#E5E5E5]">
                    <th className="text-left py-2 text-[#737373] font-medium">时间</th>
                    <th className="text-left py-2 text-[#737373] font-medium">触发</th>
                    <th className="text-left py-2 text-[#737373] font-medium">状态</th>
                    <th className="text-left py-2 text-[#737373] font-medium">耗时</th>
                    <th className="text-left py-2 text-[#737373] font-medium">结果</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((r) => {
                    const duration = r.started_at && r.finished_at
                      ? Math.round((new Date(r.finished_at).getTime() - new Date(r.started_at).getTime()) / 1000)
                      : null
                    const total = r.result ? Object.values(r.result).reduce((a, b) => a + b, 0) : null
                    return (
                      <tr key={r.id} className="border-b border-[#F5F5F4]">
                        <td className="py-2 text-[#525252]">{r.started_at ? formatDateTime(r.started_at) : "-"}</td>
                        <td className="py-2 text-[#525252]">{r.trigger === "manual" ? "手动" : "定时"}</td>
                        <td className="py-2">
                          <span className={`px-2 py-0.5 rounded-full text-[12px] font-medium ${STATUS_MAP[r.status]?.color ?? "text-gray-600 bg-gray-50"}`}>
                            {STATUS_MAP[r.status]?.label ?? r.status}
                          </span>
                        </td>
                        <td className="py-2 text-[#525252]">{duration !== null ? `${duration}s` : "-"}</td>
                        <td className="py-2 text-[#525252]">
                          {total !== null ? `${total} 条` : r.error ? <span className="text-red-500">{r.error.slice(0, 40)}</span> : "-"}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {/* 分页 */}
            {historyPages > 1 && (
              <div className="flex justify-end gap-2 mt-4">
                <button
                  onClick={() => loadHistory(historyPage - 1)}
                  disabled={historyPage <= 1}
                  className="px-3 py-1 text-[13px] border border-[#E5E5E5] rounded hover:bg-[#F5F5F4] disabled:opacity-40"
                >
                  上一页
                </button>
                <span className="px-3 py-1 text-[13px] text-[#737373]">{historyPage}/{historyPages}</span>
                <button
                  onClick={() => loadHistory(historyPage + 1)}
                  disabled={historyPage >= historyPages}
                  className="px-3 py-1 text-[13px] border border-[#E5E5E5] rounded hover:bg-[#F5F5F4] disabled:opacity-40"
                >
                  下一页
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
