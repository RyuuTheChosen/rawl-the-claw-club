import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4">
      <h1 className="font-pixel text-4xl text-neon-red sm:text-6xl">404</h1>
      <p className="font-pixel text-xs text-muted-foreground sm:text-sm">
        STAGE NOT FOUND
      </p>
      <Link
        href="/"
        className="mt-4 inline-flex items-center justify-center rounded-md bg-neon-orange px-6 py-2.5 text-sm font-semibold text-background transition-colors hover:bg-neon-orange/90 shadow-neon-orange"
      >
        RETURN TO LOBBY
      </Link>
    </div>
  );
}
