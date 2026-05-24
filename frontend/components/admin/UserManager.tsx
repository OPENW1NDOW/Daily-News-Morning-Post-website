"use client"

import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { AdminUser } from "@/lib/types"
import { Shield, ShieldOff, User as UserIcon } from "lucide-react"

export default function UserManager() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [currentUserId, setCurrentUserId] = useState<number | null>(null)

  useEffect(() => {
    Promise.all([api.adminUsers(), api.getMe()])
      .then(([u, me]) => {
        setUsers(u)
        setCurrentUserId(me.id)
      })
      .finally(() => setLoading(false))
  }, [])

  const toggleAdmin = async (userId: number, currentIsAdmin: boolean) => {
    if (userId === currentUserId && currentIsAdmin) {
      alert("不能取消自己的管理员权限")
      return
    }
    await api.adminToggleAdmin(userId, !currentIsAdmin)
    setUsers((prev) => prev.map((u) => u.id === userId ? { ...u, is_admin: !currentIsAdmin } : u))
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="w-6 h-6 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin" /></div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-[#0F0F0F]">用户管理</h2>
        <span className="text-[13px] text-[#737373]">{users.length} 位用户</span>
      </div>

      <div className="bg-white rounded-xl border border-[#E5E5E5] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-[#E5E5E5] bg-[#FAFAF9]">
                <th className="text-left px-4 py-2.5 text-[#737373] font-medium">ID</th>
                <th className="text-left px-4 py-2.5 text-[#737373] font-medium">用户名</th>
                <th className="text-center px-4 py-2.5 text-[#737373] font-medium">角色</th>
                <th className="text-center px-4 py-2.5 text-[#737373] font-medium">收藏数</th>
                <th className="text-left px-4 py-2.5 text-[#737373] font-medium">注册时间</th>
                <th className="text-center px-4 py-2.5 text-[#737373] font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-[#F5F5F4] hover:bg-[#FAFAF9]/50">
                  <td className="px-4 py-2.5 text-[#737373]">{u.id}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-[#F5F5F4] flex items-center justify-center">
                        <UserIcon size={14} className="text-[#737373]" />
                      </div>
                      <span className="text-[#0F0F0F]">{u.username}</span>
                      {u.id === currentUserId && (
                        <span className="text-[11px] text-[#A3A3A3]">(当前)</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    {u.is_admin ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[12px] font-medium text-amber-600 bg-amber-50">
                        <Shield size={12} /> 管理员
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full text-[12px] text-[#737373] bg-[#F5F5F4]">普通用户</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-center text-[#525252]">{u.favorite_count}</td>
                  <td className="px-4 py-2.5 text-[#737373]">{u.created_at ? new Date(u.created_at).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false }) : "-"}</td>
                  <td className="px-4 py-2.5 text-center">
                    <button
                      onClick={() => toggleAdmin(u.id, u.is_admin)}
                      disabled={u.id === currentUserId && u.is_admin}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] transition-colors ${
                        u.is_admin
                          ? "border border-amber-200 text-amber-600 hover:bg-amber-50 disabled:opacity-40 disabled:cursor-not-allowed"
                          : "border border-[#E5E5E5] text-[#525252] hover:bg-[#F5F5F4]"
                      }`}
                    >
                      {u.is_admin ? <ShieldOff size={13} /> : <Shield size={13} />}
                      {u.is_admin ? "取消管理员" : "设为管理员"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
