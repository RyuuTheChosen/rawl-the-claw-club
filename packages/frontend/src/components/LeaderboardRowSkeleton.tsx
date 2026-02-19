export function LeaderboardRowSkeleton() {
  return (
    <tr className="border-b border-border/50 animate-pulse">
      <td className="px-4 py-3"><div className="h-4 w-6 rounded bg-muted" /></td>
      <td className="px-4 py-3">
        <div className="h-4 w-24 rounded bg-muted" />
        <div className="mt-1 h-3 w-16 rounded bg-muted" />
      </td>
      <td className="px-4 py-3"><div className="h-4 w-14 rounded bg-muted" /></td>
      <td className="px-4 py-3 text-right"><div className="ml-auto h-4 w-12 rounded bg-muted" /></td>
      <td className="hidden px-4 py-3 text-right sm:table-cell"><div className="ml-auto h-4 w-10 rounded bg-muted" /></td>
      <td className="hidden px-4 py-3 text-right sm:table-cell"><div className="ml-auto h-4 w-8 rounded bg-muted" /></td>
    </tr>
  );
}
