"use client"

import { Suspense, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { api } from "@/lib/api"
import { setToken } from "@/lib/auth"
import { SamoyedAvatar } from "@/components/SamoyedAvatar"

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [isLogin, setIsLogin] = useState(true)
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      const res = isLogin
        ? await api.login(username, password)
        : await api.register(username, password)
      setToken(res.token)
      const next = searchParams.get("next")
      // 只允许站内路径，防止开放重定向
      router.push(next && next.startsWith("/") && !next.startsWith("//") ? next : "/")
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#FAFAF9] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <SamoyedAvatar size={56} className="mx-auto mb-4 ring-2 ring-white shadow-sm" />
          <h1 className="font-serif text-[28px] font-semibold text-[#0F0F0F]">
            {isLogin ? "欢迎回来" : "创建账号"}
          </h1>
          <p className="text-[14px] text-[#A3A3A3] mt-2">
            {isLogin ? "登录后可管理你的收藏" : "注册后即可收藏新闻"}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="用户名"
              required
              minLength={2}
              maxLength={20}
              className="w-full px-4 py-3 bg-white border border-stone-200 rounded-xl text-[14px] text-[#0F0F0F] placeholder:text-[#A3A3A3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-400 focus-visible:ring-offset-1 transition-colors"
            />
          </div>
          <div>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="密码"
              required
              minLength={4}
              className="w-full px-4 py-3 bg-white border border-stone-200 rounded-xl text-[14px] text-[#0F0F0F] placeholder:text-[#A3A3A3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-400 focus-visible:ring-offset-1 transition-colors"
            />
          </div>

          {error && (
            <p className="text-[13px] text-red-500">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-[#0F0F0F] text-white text-[14px] font-medium rounded-xl hover:bg-[#262626] transition-colors disabled:opacity-50"
          >
            {loading ? "请稍候..." : isLogin ? "登录" : "注册"}
          </button>
        </form>

        <p className="text-center text-[13px] text-[#A3A3A3] mt-6">
          {isLogin ? "没有账号？" : "已有账号？"}
          <button
            onClick={() => { setIsLogin(!isLogin); setError("") }}
            className="text-[#2563EB] hover:underline ml-1"
          >
            {isLogin ? "立即注册" : "去登录"}
          </button>
        </p>

        <p className="text-center mt-4">
          <Link href="/" className="text-[13px] text-[#A3A3A3] hover:text-[#0F0F0F]">
            返回首页
          </Link>
        </p>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  )
}
