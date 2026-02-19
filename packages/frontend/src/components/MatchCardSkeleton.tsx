export function MatchCardSkeleton() {
  return (
    <div className="arcade-border p-4 animate-pulse">
      {/* Top row */}
      <div className="mb-3 flex items-center justify-between">
        <div className="h-3 w-12 rounded bg-muted" />
        <div className="h-4 w-16 rounded bg-muted" />
      </div>
      {/* VS row */}
      <div className="mb-3 flex items-center justify-between">
        <div className="h-4 w-20 rounded bg-muted" />
        <div className="h-3 w-6 rounded bg-muted" />
        <div className="h-4 w-20 rounded bg-muted" />
      </div>
      {/* Bottom row */}
      <div className="flex items-center justify-between">
        <div className="h-3 w-8 rounded bg-muted" />
        <div className="h-3 w-14 rounded bg-muted" />
        <div className="h-3 w-10 rounded bg-muted" />
      </div>
    </div>
  );
}
