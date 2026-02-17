"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import dynamic from "next/dynamic";
import { Swords, Trophy, LayoutDashboard, Menu, Monitor } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useUiStore } from "@/stores/uiStore";
import { cn } from "@/lib/utils";

const WalletMultiButton = dynamic(
  () =>
    import("@solana/wallet-adapter-react-ui").then(
      (mod) => mod.WalletMultiButton,
    ),
  { ssr: false },
);

const navLinks = [
  { href: "/lobby", label: "Lobby", icon: Swords },
  { href: "/leaderboard", label: "Scores", icon: Trophy },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
];

export function Navbar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const { crtEnabled, toggleCrt } = useUiStore();

  return (
    <nav className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
        {/* Logo + Desktop Links */}
        <div className="flex items-center gap-8">
          <Link
            href="/"
            className="font-pixel text-base text-neon-orange text-glow-orange tracking-wider"
          >
            RAWL
          </Link>
          <div className="hidden gap-1 md:flex">
            {navLinks.map(({ href, label, icon: Icon }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    active
                      ? "bg-neon-orange/10 text-neon-orange"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </Link>
              );
            })}
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-2">
          <button
            onClick={toggleCrt}
            className={cn(
              "rounded-md p-2 text-muted-foreground transition-colors hover:text-foreground",
              crtEnabled && "text-neon-orange",
            )}
            title={crtEnabled ? "Disable CRT effect" : "Enable CRT effect"}
          >
            <Monitor className="h-4 w-4" />
          </button>

          <WalletMultiButton />

          {/* Mobile hamburger */}
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <button className="rounded-md p-2 text-muted-foreground md:hidden">
                <Menu className="h-5 w-5" />
              </button>
            </SheetTrigger>
            <SheetContent side="right" className="w-64 bg-background border-border">
              <nav className="mt-8 flex flex-col gap-2">
                {navLinks.map(({ href, label, icon: Icon }) => {
                  const active = pathname === href;
                  return (
                    <Link
                      key={href}
                      href={href}
                      onClick={() => setOpen(false)}
                      className={cn(
                        "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                        active
                          ? "bg-neon-orange/10 text-neon-orange"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {label}
                    </Link>
                  );
                })}
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </nav>
  );
}
