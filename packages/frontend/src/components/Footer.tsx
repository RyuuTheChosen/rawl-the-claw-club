"use client";

import Link from "next/link";
import { Twitter, Github } from "lucide-react";

const SOCIAL_LINKS = [
  { label: "Twitter", href: "https://x.com/RawlClawClub", icon: Twitter },
  { label: "GitHub", href: "https://github.com/RyuuTheChosen/rawl-the-claw-club", icon: Github },
] as const;

const NAV_LINKS = [
  { href: "/lobby", label: "Lobby" },
  { href: "/leaderboard", label: "Scores" },
  { href: "/bets", label: "Bets" },
  { href: "/dashboard", label: "Dashboard" },
];

export function Footer() {
  return (
    <footer aria-label="Site footer" className="border-t border-border bg-background/60">
      <div className="mx-auto flex max-w-7xl flex-col items-center gap-6 px-4 py-8 sm:flex-row sm:justify-between">
        {/* Left: branding */}
        <div className="flex flex-col items-center gap-2 sm:items-start">
          <span className="font-pixel text-sm text-neon-orange text-glow-orange">RAWL</span>
          <span className="text-xs text-muted-foreground">Powered by Solana</span>
        </div>

        {/* Center: nav */}
        <nav className="flex flex-wrap justify-center gap-4">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Right: socials */}
        <div className="flex items-center gap-3">
          {SOCIAL_LINKS.map((s) => (
            <a
              key={s.label}
              href={s.href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground transition-colors hover:text-foreground"
              aria-label={s.label}
            >
              <s.icon className="h-4 w-4" />
            </a>
          ))}
        </div>
      </div>

      {/* Bottom */}
      <div className="border-t border-border py-4">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-center gap-4 px-4 text-xs text-muted-foreground">
          <span>&copy; {new Date().getFullYear()} Rawl</span>
          <a href="#" className="hover:text-foreground">Privacy Policy</a>
          <a href="#" className="hover:text-foreground">Terms of Service</a>
        </div>
      </div>
    </footer>
  );
}
