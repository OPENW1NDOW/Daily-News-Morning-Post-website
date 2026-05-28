import { Suspense } from "react"
import { NewsSkeleton } from "@/components/NewsSkeleton"
import { HomeContent } from "./HomeContent"

export const dynamic = "force-dynamic"

export default function HomePage() {
  return (
    <main className="min-h-screen bg-[#FAFAF9]">
      <Suspense
        fallback={
          <div className="max-w-7xl mx-auto px-6 py-10">
            <NewsSkeleton />
          </div>
        }
      >
        <HomeContent />
      </Suspense>
    </main>
  )
}
