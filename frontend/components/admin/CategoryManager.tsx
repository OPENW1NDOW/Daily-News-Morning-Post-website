"use client"

import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { CategoryConfig } from "@/lib/types"
import { Edit2, Save, X } from "lucide-react"

export default function CategoryManager() {
  const [categories, setCategories] = useState<CategoryConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [editKey, setEditKey] = useState<string | null>(null)
  const [editName, setEditName] = useState("")
  const [editDesc, setEditDesc] = useState("")

  useEffect(() => {
    api.adminCategories().then(setCategories).finally(() => setLoading(false))
  }, [])

  const startEdit = (cat: CategoryConfig) => {
    setEditKey(cat.key)
    setEditName(cat.name)
    setEditDesc(cat.description)
  }

  const saveEdit = async () => {
    if (!editKey) return
    await api.adminUpdateCategory(editKey, { name: editName, description: editDesc })
    setCategories((prev) => prev.map((c) => c.key === editKey ? { ...c, name: editName, description: editDesc } : c))
    setEditKey(null)
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="w-6 h-6 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin" /></div>
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-[#0F0F0F]">板块管理</h2>

      <div className="space-y-3">
        {categories.map((cat) => (
          <div key={cat.key} className="bg-white rounded-xl border border-[#E5E5E5] p-4">
            {editKey === cat.key ? (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <span className="text-[12px] text-[#A3A3A3] font-mono w-24 shrink-0">{cat.key}</span>
                  <input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="flex-1 px-3 py-1.5 border border-[#D4D4D4] rounded-lg text-[13px]"
                    placeholder="板块名称"
                  />
                </div>
                <textarea
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-1.5 border border-[#D4D4D4] rounded-lg text-[13px] resize-none"
                  placeholder="板块描述"
                />
                <div className="flex gap-2">
                  <button onClick={saveEdit} className="flex items-center gap-1.5 px-3 py-1.5 bg-[#2563EB] text-white rounded-lg text-[12px] hover:bg-[#1D4ED8]">
                    <Save size={13} /> 保存
                  </button>
                  <button onClick={() => setEditKey(null)} className="flex items-center gap-1.5 px-3 py-1.5 border border-[#E5E5E5] rounded-lg text-[12px] hover:bg-[#F5F5F4]">
                    <X size={13} /> 取消
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-[14px] font-medium text-[#0F0F0F]">{cat.name}</h3>
                    <span className="text-[11px] text-[#A3A3A3] font-mono">{cat.key}</span>
                  </div>
                  <p className="text-[13px] text-[#737373] mt-1">{cat.description}</p>
                </div>
                <button
                  onClick={() => startEdit(cat)}
                  className="p-1.5 border border-[#E5E5E5] rounded hover:bg-[#F5F5F4]"
                >
                  <Edit2 size={14} className="text-[#525252]" />
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
