"use client"

const GRADIENTS: Record<string, { from: string; via: string; to: string; label: string }> = {
  ai:            { from: "#6366F1", via: "#8B5CF6", to: "#A855F7", label: "AI" },      // 靛紫
  tech:          { from: "#0EA5E9", via: "#0284C7", to: "#1D4ED8", label: "TECH" },    // 天蓝→钴蓝
  policy:        { from: "#475569", via: "#334155", to: "#0F172A", label: "POLICY" },  // 石墨灰蓝
  research:      { from: "#A855F7", via: "#C026D3", to: "#DB2777", label: "RES" },     // 紫红
  business:      { from: "#CA8A04", via: "#D97706", to: "#B45309", label: "BIZ" },     // 琥珀金
  international: { from: "#0D9488", via: "#059669", to: "#047857", label: "WORLD" },   // 青翠绿
  chip:          { from: "#06B6D4", via: "#14B8A6", to: "#2DD4BF", label: "CHIP" },    // 青绿
  robotics:      { from: "#F97316", via: "#EA580C", to: "#DC2626", label: "ROBOT" },   // 橙红
  security:      { from: "#E11D48", via: "#BE123C", to: "#881337", label: "SEC" },     // 玫红酒红
  social:        { from: "#EC4899", via: "#F472B6", to: "#FB7185", label: "SOCIAL" },  // 粉
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
