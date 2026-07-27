"use client"

import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { XAccount, XFollowingStatus } from "@/lib/types"
import { formatDateTime } from "@/lib/utils"
import { RefreshCw, Loader2 } from "lucide-react"

function formatTime(iso: string | null): string {
  if (!iso) return "—"
  return formatDateTime(iso)
}

export default function XFollowingManager() {
  const [accounts, setAccounts] = useState<XAccount[]>([])
  const [status, setStatus] = useState<XFollowingStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [syncError, setSyncError] = useState<string | null>(null)

  const load = async () => {
    const [accts, st] = await Promise.all([
      api.adminXFollowingAccounts(),
      api.adminXFollowingStatus(),
    ])
    setAccounts(accts)
    setStatus(st)
  }

  useEffect(() => {
    load().finally(() => setLoading(false))
  }, [])

  const toggleEnabled = async (id: number, enabled: boolean) => {
    await api.adminPatchXFollowingAccount(id, { enabled })
    setAccounts((prev) => prev.map((a) => (a.id === id ? { ...a, enabled } : a)))
  }

  const handleSync = async () => {
    setSyncing(true)
    setSyncError(null)
    try {
      await api.adminSyncXFollowing()
      await load()
    } catch (e) {
      setSyncError(e instanceof Error ? e.message : String(e))
    } finally {
      setSyncing(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const followingError = status?.following?.error ?? null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-[#0F0F0F]">X Following</h2>
        <div className="flex items-center gap-3">
          <span className="text-[13px] text-[#737373]">{accounts.length} 个账号</span>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#2563EB] text-white rounded-lg text-[13px] hover:bg-[#1D4ED8] disabled:opacity-50 transition-colors"
          >
            {syncing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            同步 Following
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-[#E5E5E5] px-4 py-3 flex flex-wrap gap-x-6 gap-y-2 text-[13px]">
        <div className="flex items-center gap-2">
          <span className="text-[#737373]">Cookie</span>
          <span className={status?.cookie_configured ? "text-green-600 font-medium" : "text-red-600 font-medium"}>
            {status?.cookie_configured ? "已配置" : "未配置"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[#737373]">上次同步</span>
          <span className="text-[#0F0F0F]">{formatTime(status?.last_synced_at ?? null)}</span>
        </div>
        {followingError && (
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-[#737373] shrink-0">Following 错误</span>
            <span className="text-red-600 truncate" title={followingError}>{followingError}</span>
          </div>
        )}
        {syncError && (
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-[#737373] shrink-0">同步失败</span>
            <span className="text-red-600 truncate" title={syncError}>{syncError}</span>
          </div>
        )}
      </div>

      <div className="bg-white rounded-xl border border-[#E5E5E5] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-[#E5E5E5] bg-[#FAFAF9]">
                <th className="text-left px-4 py-2.5 text-[#737373] font-medium">Handle</th>
                <th className="text-left px-4 py-2.5 text-[#737373] font-medium">显示名</th>
                <th className="text-center px-4 py-2.5 text-[#737373] font-medium">Following</th>
                <th className="text-center px-4 py-2.5 text-[#737373] font-medium">启用</th>
              </tr>
            </thead>
            <tbody>
              {accounts.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-[#737373]">
                    暂无账号，点击「同步 Following」从 X 拉取
                  </td>
                </tr>
              ) : (
                accounts.map((a) => (
                  <tr key={a.id} className="border-b border-[#F5F5F4] hover:bg-[#FAFAF9]/50">
                    <td className="px-4 py-2.5 text-[#0F0F0F] font-mono text-[12px]">@{a.handle}</td>
                    <td className="px-4 py-2.5 text-[#0F0F0F]">{a.display_name || "—"}</td>
                    <td className="px-4 py-2.5 text-center">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[12px] font-medium ${
                          a.is_following
                            ? "text-green-600 bg-green-50"
                            : "text-gray-500 bg-gray-50"
                        }`}
                      >
                        {a.is_following ? "关注中" : "已取消"}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <button
                        onClick={() => toggleEnabled(a.id, !a.enabled)}
                        className={`w-9 h-5 rounded-full transition-colors ${a.enabled ? "bg-[#2563EB]" : "bg-[#D4D4D4]"}`}
                      >
                        <div
                          className={`w-4 h-4 bg-white rounded-full shadow-sm transition-transform ${
                            a.enabled ? "translate-x-4" : "translate-x-0.5"
                          }`}
                        />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
