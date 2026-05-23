"use client"

import { useEffect, useState, useCallback } from "react"
import { api } from "@/lib/api"
import type { AdminNewsItem, Category, NewsItem } from "@/lib/types"
import { Edit2, Trash2, X, ChevronLeft, ChevronRight } from "lucide-react"

export default function NewsManager() {
  const [items, setItems] = useState<AdminNewsItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [dateFilter, setDateFilter] = useState("")
  const [catFilter, setCatFilter] = useState("")
  const [categories, setCategories] = useState<Category[]>([])
  const [editItem, setEditItem] = useState<NewsItem | null>(null)
  const [editTitle, setEditTitle] = useState("")
  const [editSummary, setEditSummary] = useState("")
  const [editImportance, setEditImportance] = useState(50)

  const loadNews = useCallback((p = 1) => {
    setLoading(true)
    api.adminNews({ date: dateFilter || undefined, category: catFilter || undefined, page: p })
      .then((res) => { setItems(res.items); setTotal(res.total); setPage(res.page); setPages(res.pages) })
      .finally(() => setLoading(false))
  }, [dateFilter, catFilter])

  useEffect(() => {
    api.getCategories().then(setCategories)
  }, [])

  useEffect(() => { loadNews(1) }, [loadNews])

  const handleDelete = async (id: number) => {
    if (!confirm("确定删除这条新闻？关联的收藏也会被删除。")) return
    await api.adminDeleteNews(id)
    setItems((prev) => prev.filter((n) => n.id !== id))
    setTotal((prev) => prev - 1)
  }

  const openEdit = async (id: number) => {
    const detail = await api.adminGetNews(id)
    setEditItem(detail)
    setEditTitle(detail.title)
    setEditSummary(detail.summary ?? "")
    setEditImportance(detail.importance)
  }

  const saveEdit = async () => {
    if (!editItem) return
    await api.adminUpdateNews(editItem.id, {
      title: editTitle,
      summary: editSummary,
      importance: editImportance,
    })
    setItems((prev) => prev.map((n) => n.id === editItem.id ? { ...n, title: editTitle, summary: editSummary, importance: editImportance } : n))
    setEditItem(null)
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-[#0F0F0F]">新闻管理</h2>

      {/* 筛选 */}
      <div className="flex items-end gap-4">
        <div>
          <label className="block text-[12px] text-[#737373] mb-1">日期</label>
          <input
            type="date"
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
            className="px-3 py-1.5 border border-[#D4D4D4] rounded-lg text-[13px]"
          />
        </div>
        <div>
          <label className="block text-[12px] text-[#737373] mb-1">板块</label>
          <select
            value={catFilter}
            onChange={(e) => setCatFilter(e.target.value)}
            className="px-3 py-1.5 border border-[#D4D4D4] rounded-lg text-[13px] bg-white"
          >
            <option value="">全部</option>
            {categories.map((c) => (
              <option key={c.key} value={c.key}>{c.name}</option>
            ))}
          </select>
        </div>
        <button
          onClick={() => { setDateFilter(""); setCatFilter("") }}
          className="px-3 py-1.5 text-[13px] border border-[#E5E5E5] rounded-lg hover:bg-[#F5F5F4]"
        >
          重置
        </button>
        <span className="text-[13px] text-[#737373] ml-auto">共 {total} 条</span>
      </div>

      {/* 列表 */}
      <div className="bg-white rounded-xl border border-[#E5E5E5] overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-32"><div className="w-6 h-6 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin" /></div>
        ) : items.length === 0 ? (
          <p className="text-center text-[13px] text-[#A3A3A3] py-8">暂无数据</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[#E5E5E5] bg-[#FAFAF9]">
                  <th className="text-left px-4 py-2.5 text-[#737373] font-medium">标题</th>
                  <th className="text-left px-4 py-2.5 text-[#737373] font-medium">板块</th>
                  <th className="text-center px-4 py-2.5 text-[#737373] font-medium">重要度</th>
                  <th className="text-left px-4 py-2.5 text-[#737373] font-medium">日期</th>
                  <th className="text-center px-4 py-2.5 text-[#737373] font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((n) => (
                  <tr key={n.id} className="border-b border-[#F5F5F4] hover:bg-[#FAFAF9]/50">
                    <td className="px-4 py-2.5 max-w-[300px]">
                      <span className="text-[#0F0F0F] truncate block" title={n.title}>{n.title}</span>
                    </td>
                    <td className="px-4 py-2.5 text-[#737373]">{n.category}</td>
                    <td className="px-4 py-2.5 text-center text-[#525252]">{n.importance}</td>
                    <td className="px-4 py-2.5 text-[#737373]">{n.date}</td>
                    <td className="px-4 py-2.5 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <button onClick={() => openEdit(n.id)} className="p-1.5 border border-[#E5E5E5] rounded hover:bg-[#F5F5F4]">
                          <Edit2 size={14} className="text-[#525252]" />
                        </button>
                        <button onClick={() => handleDelete(n.id)} className="p-1.5 border border-[#E5E5E5] rounded hover:bg-red-50 hover:border-red-200">
                          <Trash2 size={14} className="text-[#525252] hover:text-red-500" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 分页 */}
        {pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-[#F5F5F4]">
            <span className="text-[12px] text-[#737373]">第 {page} / {pages} 页</span>
            <div className="flex gap-2">
              <button onClick={() => loadNews(page - 1)} disabled={page <= 1} className="p-1.5 border border-[#E5E5E5] rounded hover:bg-[#F5F5F4] disabled:opacity-40">
                <ChevronLeft size={16} />
              </button>
              <button onClick={() => loadNews(page + 1)} disabled={page >= pages} className="p-1.5 border border-[#E5E5E5] rounded hover:bg-[#F5F5F4] disabled:opacity-40">
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 编辑弹窗 */}
      {editItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[15px] font-semibold text-[#0F0F0F]">编辑新闻</h3>
              <button onClick={() => setEditItem(null)} className="p-1 hover:bg-[#F5F5F4] rounded">
                <X size={18} className="text-[#737373]" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-[12px] text-[#737373] mb-1">标题</label>
                <input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} className="w-full px-3 py-2 border border-[#D4D4D4] rounded-lg text-[13px]" />
              </div>
              <div>
                <label className="block text-[12px] text-[#737373] mb-1">摘要</label>
                <textarea value={editSummary} onChange={(e) => setEditSummary(e.target.value)} rows={3} className="w-full px-3 py-2 border border-[#D4D4D4] rounded-lg text-[13px] resize-none" />
              </div>
              <div>
                <label className="block text-[12px] text-[#737373] mb-1">重要度 ({editImportance})</label>
                <input type="range" min={0} max={100} value={editImportance} onChange={(e) => setEditImportance(Number(e.target.value))} className="w-full" />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={() => setEditItem(null)} className="px-4 py-2 text-[13px] border border-[#E5E5E5] rounded-lg hover:bg-[#F5F5F4]">取消</button>
              <button onClick={saveEdit} className="px-4 py-2 text-[13px] bg-[#2563EB] text-white rounded-lg hover:bg-[#1D4ED8]">保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
