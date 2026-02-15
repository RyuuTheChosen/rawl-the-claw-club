"use client";

import Link from "next/link";
import dynamic from "next/dynamic";

const WalletMultiButton = dynamic(
  () =>
    import("@solana/wallet-adapter-react-ui").then(
      (mod) => mod.WalletMultiButton,
    ),
  { ssr: false },
);

export function Navbar() {
  return (
    <nav className="border-b border-rawl-dark/30 bg-rawl-dark/80 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4">
        <div className="flex items-center gap-8">
          <Link href="/" className="text-xl font-bold text-rawl-primary">
            RAWL
          </Link>
          <div className="hidden gap-6 md:flex">
            <Link
              href="/lobby"
              className="text-sm text-rawl-light/70 transition hover:text-rawl-light"
            >
              Lobby
            </Link>
            <Link
              href="/leaderboard"
              className="text-sm text-rawl-light/70 transition hover:text-rawl-light"
            >
              Leaderboard
            </Link>
            <Link
              href="/dashboard"
              className="text-sm text-rawl-light/70 transition hover:text-rawl-light"
            >
              Dashboard
            </Link>
          </div>
        </div>
        <WalletMultiButton className="!bg-rawl-primary !text-rawl-dark hover:!bg-rawl-primary/80" />
      </div>
    </nav>
  );
}
