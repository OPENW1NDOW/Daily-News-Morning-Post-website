"use client"

import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { SystemSettings as SettingsData } from "@/lib/types"
import { Save, AlertTriangle, Heart } from "lucide-react"

export default function SystemSettings() {
  const [settings, setSettings] = useState<SettingsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [healthOk, setHealthOk] = useState<boolean | null>(null)

  // 编辑字段
  const [baseUrl, setBaseUrl] = useState("")
  const [model, setModel] = useState("")
  const [proxyUrl, setProxyUrl] = useState("")
  const [apiKey, setApiKey] = useState("")

  useEffect(() => {
    api.adminSettings().then((s) => {
      setSettings(s)
      setBaseUrl(s.llm_base_url)
      setModel(s.llm_model)
      setProxyUrl(s.proxy_url)
    }).finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)
    try {
      const data: Record<string, string> = {}
      if (baseUrl !== settings?.llm_base_url) data.llm_base_url = baseUrl
      if (model !== settings?.llm_model) data.llm_model = model
      if (proxyUrl !== settings?.proxy_url) data.proxy_url = proxyUrl
      if (apiKey) data.llm_api_key = apiKey

      if (Object.keys(data).length === 0) {
        setMessage("没有变更")
        return
      }
      const res = await api.adminUpdateSettings(data)
      setMessage(res.message)
      setApiKey("")
      // 重新加载
      const fresh = await api.adminSettings()
      setSettings(fresh)
    } catch {
      setMessage("保存失败")
    } finally {
      setSaving(false)
    }
  }

  const checkHealth = async () => {
    try {
      const res = await api.health()
      setHealthOk(res.ok)
    } catch {
      setHealthOk(false)
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="w-6 h-6 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin" /></div>
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-[#0F0F0F]">系统设置</h2>

      {/* 健康检查 */}
      <div className="bg-white rounded-xl border border-[#E5E5E5] p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-medium text-[#0F0F0F]">服务状态</h3>
            <p className="text-[13px] text-[#737373] mt-0.5">检查后端服务是否正常运行</p>
          </div>
          <div className="flex items-center gap-3">
            {healthOk !== null && (
              <span className={`text-[13px] ${healthOk ? "text-green-600" : "text-red-500"}`}>
                {healthOk ? "正常" : "异常"}
              </span>
            )}
            <button
              onClick={checkHealth}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-[#E5E5E5] rounded-lg text-[13px] hover:bg-[#F5F5F4]"
            >
              <Heart size={14} /> 检查
            </button>
          </div>
        </div>
      </div>

      {/* 设置表单 */}
      <div className="bg-white rounded-xl border border-[#E5E5E5] p-5">
        <h3 className="text-sm font-medium text-[#0F0F0F] mb-4">LLM 配置</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-[12px] text-[#737373] mb-1">API Key</label>
            <div className="flex items-center gap-2">
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={settings?.llm_api_key_masked ?? "****"}
                className="flex-1 px-3 py-2 border border-[#D4D4D4] rounded-lg text-[13px]"
              />
              <span className="text-[12px] text-[#A3A3A3]">当前: {settings?.llm_api_key_masked}</span>
            </div>
          </div>
          <div>
            <label className="block text-[12px] text-[#737373] mb-1">Base URL</label>
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              className="w-full px-3 py-2 border border-[#D4D4D4] rounded-lg text-[13px]"
            />
          </div>
          <div>
            <label className="block text-[12px] text-[#737373] mb-1">模型</label>
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full px-3 py-2 border border-[#D4D4D4] rounded-lg text-[13px]"
            />
          </div>
          <div>
            <label className="block text-[12px] text-[#737373] mb-1">代理地址</label>
            <input
              value={proxyUrl}
              onChange={(e) => setProxyUrl(e.target.value)}
              className="w-full px-3 py-2 border border-[#D4D4D4] rounded-lg text-[13px]"
            />
          </div>
        </div>

        {/* 警告 */}
        <div className="flex items-start gap-2 mt-4 p-3 bg-amber-50 rounded-lg">
          <AlertTriangle size={16} className="text-amber-500 shrink-0 mt-0.5" />
          <p className="text-[12px] text-amber-700">修改 API Key 或代理地址后需要重启服务才能生效。</p>
        </div>

        {/* 消息 */}
        {message && (
          <div className="mt-3 p-3 bg-blue-50 rounded-lg text-[13px] text-blue-700">{message}</div>
        )}

        <div className="mt-6">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-[#2563EB] text-white text-[13px] rounded-lg hover:bg-[#1D4ED8] disabled:opacity-50"
          >
            <Save size={16} />
            {saving ? "保存中..." : "保存设置"}
          </button>
        </div>
      </div>
    </div>
  )
}
