"use client"

import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { SourceDetail } from "@/lib/types"
import { RefreshCw, CheckCircle2, XCircle, Loader2, ExternalLink } from "lucide-react"

const STATUS_BADGE: Record<string, { label: string; color: string }> = {
  ok: { label: "正常", color: "text-green-600 bg-green-50" },
  error: { label: "失败", color: "text-red-600 bg-red-50" },
  unknown: { label: "未知", color: "text-gray-500 bg-gray-50" },
}

export default function SourceManager() {
  const [sources, setSources] = useState<SourceDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState<Record<number, boolean>>({})
  const [testResults, setTestResults] = useState<Record<number, { ok: boolean; error?: string | null }>>({})
  const [editId, setEditId] = useState<number | null>(null)
  const [editName, setEditName] = useState("")
  const [editUrl, setEditUrl] = useState("")

  const loadSources = () => {
    api.adminSources().then(setSources).finally(() => setLoading(false))
  }

  useEffect(() => { loadSources() }, [])

  const toggleField = async (id: number, field: "enabled" | "use_proxy", value: boolean) => {
    await api.adminUpdateSource(id, { [field]: value })
    setSources((prev) => prev.map((s) => s.id === id ? { ...s, [field]: value } : s))
  }

  const handleTest = async (id: number) => {
    setTesting((prev) => ({ ...prev, [id]: true }))
    setTestResults((prev) => { const next = { ...prev }; delete next[id]; return next })
    try {
      const res = await api.adminTestSource(id)
      setTestResults((prev) => ({ ...prev, [id]: res }))
    } finally {
      setTesting((prev) => ({ ...prev, [id]: false }))
    }
  }

  const startEdit = (s: SourceDetail) => {
    setEditId(s.id)
    setEditName(s.name)
    setEditUrl(s.url)
  }

  const saveEdit = async () => {
    if (editId === null) return
    await api.adminUpdateSource(editId, { name: editName, url: editUrl })
    setSources((prev) => prev.map((s) => s.id === editId ? { ...s, name: editName, url: editUrl } : s))
    setEditId(null)
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="w-6 h-6 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin" /></div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-[#0F0F0F]">数据源管理</h2>
        <span className="text-[13px] text-[#737373]">{sources.length} 个源</span>
      </div>

      <div className="bg-white rounded-xl border border-[#E5E5E5] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-[#E5E5E5] bg-[#FAFAF9]">
                <th className="text-left px-4 py-2.5 text-[#737373] font-medium">名称</th>
                <th className="text-left px-4 py-2.5 text-[#737373] font-medium">Key</th>
                <th className="text-left px-4 py-2.5 text-[#737373] font-medium">URL</th>
                <th className="text-center px-4 py-2.5 text-[#737373] font-medium">启用</th>
                <th className="text-center px-4 py-2.5 text-[#737373] font-medium">代理</th>
                <th className="text-center px-4 py-2.5 text-[#737373] font-medium">状态</th>
                <th className="text-center px-4 py-2.5 text-[#737373] font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => {
                const badge = STATUS_BADGE[s.last_status] ?? STATUS_BADGE.unknown
                const testRes = testResults[s.id]
                return (
                  <tr key={s.id} className="border-b border-[#F5F5F4] hover:bg-[#FAFAF9]/50">
                    <td className="px-4 py-2.5">
                      {editId === s.id ? (
                        <input value={editName} onChange={(e) => setEditName(e.target.value)} className="w-full px-2 py-1 border border-[#D4D4D4] rounded text-[13px]" />
                      ) : (
                        <span className="text-[#0F0F0F]">{s.name}</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-[#737373] font-mono text-[12px]">{s.key}</td>
                    <td className="px-4 py-2.5 max-w-[200px]">
                      {editId === s.id ? (
                        <input value={editUrl} onChange={(e) => setEditUrl(e.target.value)} className="w-full px-2 py-1 border border-[#D4D4D4] rounded text-[13px]" />
                      ) : (
                        <span className="text-[#737373] truncate block" title={s.url}>{s.url}</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <button
                        onClick={() => toggleField(s.id, "enabled", !s.enabled)}
                        className={`w-9 h-5 rounded-full transition-colors ${s.enabled ? "bg-[#2563EB]" : "bg-[#D4D4D4]"}`}
                      >
                        <div className={`w-4 h-4 bg-white rounded-full shadow-sm transition-transform ${s.enabled ? "translate-x-4" : "translate-x-0.5"}`} />
                      </button>
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <button
                        onClick={() => toggleField(s.id, "use_proxy", !s.use_proxy)}
                        className={`w-9 h-5 rounded-full transition-colors ${s.use_proxy ? "bg-[#2563EB]" : "bg-[#D4D4D4]"}`}
                      >
                        <div className={`w-4 h-4 bg-white rounded-full shadow-sm transition-transform ${s.use_proxy ? "translate-x-4" : "translate-x-0.5"}`} />
                      </button>
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-[12px] font-medium ${badge.color}`}>{badge.label}</span>
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        {editId === s.id ? (
                          <>
                            <button onClick={saveEdit} className="px-2 py-1 bg-[#2563EB] text-white rounded text-[12px] hover:bg-[#1D4ED8]">保存</button>
                            <button onClick={() => setEditId(null)} className="px-2 py-1 border border-[#E5E5E5] rounded text-[12px] hover:bg-[#F5F5F4]">取消</button>
                          </>
                        ) : (
                          <>
                            <button onClick={() => startEdit(s)} className="px-2 py-1 border border-[#E5E5E5] rounded text-[12px] hover:bg-[#F5F5F4]">编辑</button>
                            <button
                              onClick={() => handleTest(s.id)}
                              disabled={testing[s.id]}
                              className="flex items-center gap-1 px-2 py-1 border border-[#E5E5E5] rounded text-[12px] hover:bg-[#F5F5F4] disabled:opacity-50"
                            >
                              {testing[s.id] ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                              测试
                            </button>
                          </>
                        )}
                        {testRes && (
                          <span className={testRes.ok ? "text-green-600" : "text-red-500"}>
                            {testRes.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
