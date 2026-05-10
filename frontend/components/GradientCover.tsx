"use client"

const GRADIENTS: Record<string, { from: string; via: string; to: string; label: string }> = {
  ai:            { from: "#6366F1", via: "#8B5CF6", to: "#A855F7", label: "AI" },         // 靛紫
  ai_paper:      { from: "#7C3AED", via: "#9333EA", to: "#C026D3", label: "PAPER" },      // 深紫→品红
  tech:          { from: "#0EA5E9", via: "#0284C7", to: "#1D4ED8", label: "TECH" },       // 天蓝→钴蓝
  internet:      { from: "#06B6D4", via: "#0891B2", to: "#0E7490", label: "NET" },        // 青色
  business:      { from: "#CA8A04", via: "#D97706", to: "#B45309", label: "BIZ" },        // 琥珀金
  finance:       { from: "#DC2626", via: "#B91C1C", to: "#991B1B", label: "FIN" },        // 正红
  international: { from: "#0D9488", via: "#059669", to: "#047857", label: "WORLD" },      // 青翠绿
  social:        { from: "#EC4899", via: "#F472B6", to: "#FB7185", label: "SOCIAL" },     // 粉
  other:         { from: "#6B7280", via: "#4B5563", to: "#374151", label: "—" },
}

interface Props {
  categoryKey: string
  className?: string
  size?: "lg" | "md" | "sm"
}

export function GradientCover({ categoryKey, className = "", size = "md" }: Props) {
  const g = GRADIENTS[categoryKey] ?? GRADIENTS.other
  const fontSize = size === "lg" ? "text-[72px]" : size === "md" ? "text-[44px]" : "text-[28px]"

  return (
    <div
      className={`relative overflow-hidden ${className}`}
      style={{
        backgroundImage: `linear-gradient(135deg, ${g.from} 0%, ${g.via} 50%, ${g.to} 100%)`,
      }}
    >
      <div
        className="absolute inset-0 opacity-30"
        style={{
          backgroundImage:
            "radial-gradient(circle at 20% 20%, rgba(255,255,255,0.4) 0%, transparent 50%), radial-gradient(circle at 80% 80%, rgba(0,0,0,0.2) 0%, transparent 50%)",
        }}
      />
      <div className="absolute inset-0 flex items-center justify-center">
        <span
          className={`font-black tracking-tighter text-white/20 select-none ${fontSize}`}
          style={{ fontFamily: "var(--font-geist-mono)" }}
        >
          {g.label}
        </span>
      </div>
    </div>
  )
}

export function gradientFor(categoryKey: string) {
  return GRADIENTS[categoryKey] ?? GRADIENTS.other
}
