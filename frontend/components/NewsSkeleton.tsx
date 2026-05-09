export function NewsSkeleton() {
  return (
    <div className="space-y-10">
      <div className="bg-white border border-stone-200 rounded-3xl p-8 md:p-12 animate-pulse">
        <div className="flex gap-3 mb-6">
          <div className="h-5 w-20 bg-stone-100 rounded-full" />
          <div className="h-5 w-16 bg-stone-100 rounded-full" />
        </div>
        <div className="h-10 bg-stone-100 rounded w-4/5 mb-3" />
        <div className="h-10 bg-stone-100 rounded w-3/5 mb-6" />
        <div className="h-4 bg-stone-100 rounded w-full mb-2" />
        <div className="h-4 bg-stone-100 rounded w-4/5" />
      </div>

      <div>
        <div className="flex items-center gap-3 mb-5 pb-3 border-b border-stone-200">
          <div className="w-2.5 h-2.5 rounded-full bg-stone-100 animate-pulse" />
          <div className="h-6 w-24 bg-stone-100 rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="bg-white border border-stone-200 rounded-2xl p-6 animate-pulse">
              <div className="h-3 w-14 bg-stone-100 rounded mb-3" />
              <div className="h-5 bg-stone-100 rounded w-5/6 mb-2" />
              <div className="h-5 bg-stone-100 rounded w-3/4 mb-3" />
              <div className="h-3 bg-stone-100 rounded w-full mb-1" />
              <div className="h-3 bg-stone-100 rounded w-2/3 mb-4" />
              <div className="h-3 bg-stone-100 rounded w-1/3 pt-3" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
