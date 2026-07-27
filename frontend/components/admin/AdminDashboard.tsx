"use client"

import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { AdminDashboard as DashboardData } from "@/lib/types"
import { formatDateTime } from "@/lib/utils"
import { Newspaper, Users, Rss, Activity } from "lucide-react"

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  success: { label: "成功", color: "text-green-600 bg-green-50" },
  error: { label: "失败", color: "text-red-600 bg-red-50" },
  running: { label: "运行中", color: "text-blue-600 bg-blue-50" },
}

export default function AdminDashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.adminDashboard().then(setData).finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="w-6 h-6 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin" /></div>
  }
  if (!data) return <p className="text-sm text-[#737373]">加载失败</p>

  const stats = [
    { label: "今日新闻", value: data.today_count, icon: <Newspaper size={20} />, color: "bg-blue-50 text-blue-600" },
    { label: "用户总数", value: data.user_count, icon: <Users size={20} />, color: "bg-purple-50 text-purple-600" },
    { label: "数据源", value: `${data.sources_ok}/${data.sources_total}`, icon: <Rss size={20} />, color: "bg-green-50 text-green-600" },
    { label: "历史新闻", value: data.total_news, icon: <Activity size={20} />, color: "bg-amber-50 text-amber-600" },
  ]

  const maxCount = Math.max(...data.category_distribution.map((c) => c.count), 1)

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-[#0F0F0F]">仪表盘</h2>

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="bg-white rounded-xl border border-[#E5E5E5] p-4">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${s.color}`}>
                {s.icon}
              </div>
              <div>
                <p className="text-[12px] text-[#737373]">{s.label}</p>
                <p className="text-xl font-semibold text-[#0F0F0F]">{s.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* 分类分布 */}
        <div className="bg-white rounded-xl border border-[#E5E5E5] p-5">
          <h3 className="text-sm font-medium text-[#0F0F0F] mb-4">今日分类分布</h3>
          {data.category_distribution.length === 0 ? (
            <p className="text-[13px] text-[#A3A3A3]">今日暂无数据</p>
          ) : (
            <div className="space-y-3">
              {data.category_distribution.map((cat) => (
                <div key={cat.key} className="flex items-center gap-3">
                  <span className="text-[13px] text-[#525252] w-24 shrink-0 truncate">{cat.name}</span>
                  <div className="flex-1 h-5 bg-[#F5F5F4] rounded overflow-hidden">
                    <div
                      className="h-full bg-[#2563EB] rounded transition-all"
                      style={{ width: `${(cat.count / maxCount) * 100}%` }}
                    />
                  </div>
                  <span className="text-[13px] font-medium text-[#0F0F0F] w-8 text-right">{cat.count}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 最近流水线 */}
        <div className="bg-white rounded-xl border border-[#E5E5E5] p-5">
          <h3 className="text-sm font-medium text-[#0F0F0F] mb-4">最近一次流水线</h3>
          {!data.latest_pipeline ? (
            <p className="text-[13px] text-[#A3A3A3]">暂无运行记录</p>
          ) : (
            <div className="space-y-3">
              <div className="flex justify-between text-[13px]">
                <span className="text-[#737373]">状态</span>
                <span className={`px-2 py-0.5 rounded-full text-[12px] font-medium ${STATUS_MAP[data.latest_pipeline.status]?.color ?? "text-gray-600 bg-gray-50"}`}>
                  {STATUS_MAP[data.latest_pipeline.status]?.label ?? data.latest_pipeline.status}
                </span>
              </div>
              <div className="flex justify-between text-[13px]">
                <span className="text-[#737373]">触发方式</span>
                <span className="text-[#0F0F0F]">{data.latest_pipeline.trigger === "manual" ? "手动" : "定时"}</span>
              </div>
              <div className="flex justify-between text-[13px]">
                <span className="text-[#737373]">开始时间</span>
                <span className="text-[#0F0F0F]">{data.latest_pipeline.started_at ? formatDateTime(data.latest_pipeline.started_at) : "-"}</span>
              </div>
              {data.latest_pipeline.result && (
                <div className="flex justify-between text-[13px]">
                  <span className="text-[#737373]">写入数量</span>
                  <span className="text-[#0F0F0F]">{Object.values(data.latest_pipeline.result).reduce((a, b) => a + b, 0)} 条</span>
                </div>
              )}
              {data.latest_pipeline.error && (
                <div className="text-[13px] text-red-600 bg-red-50 rounded-lg p-3 mt-2">
                  {data.latest_pipeline.error}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 系统信息 */}
      <div className="bg-white rounded-xl border border-[#E5E5E5] p-5">
        <h3 className="text-sm font-medium text-[#0F0F0F] mb-4">系统信息</h3>
        <div className="grid grid-cols-3 gap-4 text-[13px]">
          <div>
            <span className="text-[#737373]">LLM 模型</span>
            <p className="text-[#0F0F0F] mt-1">{data.system.llm_model}</p>
          </div>
          <div>
            <span className="text-[#737373]">代理地址</span>
            <p className="text-[#0F0F0F] mt-1">{data.system.proxy_url}</p>
          </div>
          <div>
            <span className="text-[#737373]">数据库大小</span>
            <p className="text-[#0F0F0F] mt-1">{data.system.db_size_mb} MB</p>
          </div>
        </div>
      </div>
    </div>
  )
}
