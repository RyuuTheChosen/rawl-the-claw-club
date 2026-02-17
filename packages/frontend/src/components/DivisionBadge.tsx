"use client";

import { Shield, Award, Trophy, Crown } from "lucide-react";
import { cn } from "@/lib/utils";

type Division = "Bronze" | "Silver" | "Gold" | "Diamond";

const divisionConfig: Record<Division, { icon: typeof Shield; color: string; glow: string }> = {
  Bronze: { icon: Shield, color: "text-orange-400", glow: "" },
  Silver: { icon: Award, color: "text-gray-300", glow: "" },
  Gold: { icon: Trophy, color: "text-yellow-400", glow: "text-glow-orange" },
  Diamond: { icon: Crown, color: "text-neon-cyan", glow: "text-glow-cyan" },
};

interface DivisionBadgeProps {
  division: Division;
  className?: string;
  showLabel?: boolean;
}

export function DivisionBadge({ division, className, showLabel = true }: DivisionBadgeProps) {
  const config = divisionConfig[division] ?? divisionConfig.Bronze;
  const Icon = config.icon;

  return (
    <span className={cn("inline-flex items-center gap-1", config.color, config.glow, className)}>
      <Icon className="h-3.5 w-3.5" />
      {showLabel && (
        <span className="text-xs font-semibold">{division}</span>
      )}
    </span>
  );
}
