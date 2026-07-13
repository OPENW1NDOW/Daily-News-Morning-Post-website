"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { api } from "@/lib/api"
import { isAuthenticated } from "@/lib/auth"
import type { UserProfile } from "@/lib/types"
import {
  LayoutDashboard, Play, Rss, Newspaper, Users, Tags, Settings, ArrowLeft, LogOut, AtSign,
} from "lucide-react"
import { clearToken } from "@/lib/auth"

import AdminDashboard from "@/components/admin/AdminDashboard"
import PipelineControl from "@/components/admin/PipelineControl"
import SourceManager from "@/components/admin/SourceManager"
import NewsManager from "@/components/admin/NewsManager"
import UserManager from "@/components/admin/UserManager"
import CategoryManager from "@/components/admin/CategoryManager"
import SystemSettings from "@/components/admin/SystemSettings"
import XFollowingManager from "@/components/admin/XFollowingManager"

type AdminTab = "dashboard" | "pipeline" | "sources" | "x-following" | "news" | "users" | "categories" | "settings"

const TABS: { key: AdminTab; label: string; icon: React.ReactNode }[] = [
  { key: "dashboard", label: "仪表盘", icon: <LayoutDashboard size={18} /> },
  { key: "pipeline", label: "流水线", icon: <Play size={18} /> },
  { key: "sources", label: "数据源", icon: <Rss size={18} /> },
  { key: "x-following", label: "X Following", icon: <AtSign size={18} /> },
  { key: "news", label: "新闻管理", icon: <Newspaper size={18} /> },
  { key: "users", label: "用户管理", icon: <Users size={18} /> },
  { key: "categories", label: "板块管理", icon: <Tags size={18} /> },
  { key: "settings", label: "系统设置", icon: <Settings size={18} /> },
]

export default function AdminPage() {
  const router = useRouter()
  const [user, setUser] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<AdminTab>("dashboard")

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login")
      return
    }
    api.getMe()
      .then((u) => {
        if (!u.is_admin) {
          router.push("/")
          return
        }
        setUser(u)
        setLoading(false)
      })
      .catch(() => {
        clearToken()
        router.push("/login")
      })
  }, [router])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAFAF9]">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-[#737373]">加载中...</p>
        </div>
      </div>
    )
  }

  const renderTab = () => {
    switch (activeTab) {
      case "dashboard": return <AdminDashboard />
      case "pipeline": return <PipelineControl />
      case "sources": return <SourceManager />
      case "x-following": return <XFollowingManager />
      case "news": return <NewsManager />
      case "users": return <UserManager />
      case "categories": return <CategoryManager />
      case "settings": return <SystemSettings />
    }
  }

  return (
    <div className="min-h-screen bg-[#FAFAF9] flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-sm border-b border-[#E5E5E5]">
        <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="flex items-center gap-1.5 text-[#737373] hover:text-[#0F0F0F] transition-colors">
              <ArrowLeft size={16} />
              <span className="text-[13px]">返回首页</span>
            </Link>
            <div className="w-px h-4 bg-[#E5E5E5]" />
            <h1 className="text-[15px] font-semibold text-[#0F0F0F]">管理后台</h1>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[13px] text-[#737373]">{user?.username}</span>
            <button
              onClick={() => { clearToken(); router.push("/") }}
              className="flex items-center gap-1 text-[13px] text-[#737373] hover:text-[#DC2626] transition-colors"
            >
              <LogOut size={14} />
              退出
            </button>
          </div>
        </div>
      </header>

      {/* Body */}
      <div className="flex-1 max-w-[1400px] mx-auto w-full flex">
        {/* Sidebar */}
        <aside className="w-52 shrink-0 border-r border-[#E5E5E5] bg-white p-3">
          <nav className="flex flex-col gap-0.5">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] transition-colors text-left ${
                  activeTab === tab.key
                    ? "bg-[#2563EB]/10 text-[#2563EB] font-medium"
                    : "text-[#525252] hover:bg-[#F5F5F4]"
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </nav>
        </aside>

        {/* Content */}
        <main className="flex-1 p-6 overflow-auto">
          {renderTab()}
        </main>
      </div>
    </div>
  )
}
