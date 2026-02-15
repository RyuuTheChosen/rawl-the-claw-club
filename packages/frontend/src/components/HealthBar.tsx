"use client";

interface HealthBarProps {
  health: number; // 0.0 - 1.0
  side: "left" | "right";
  label?: string;
}

export function HealthBar({ health, side, label }: HealthBarProps) {
  const percent = Math.max(0, Math.min(100, health * 100));
  const colorClass =
    percent > 50 ? "bg-green-500" : percent > 25 ? "bg-yellow-500" : "bg-red-500";

  return (
    <div className="w-full">
      {label && (
        <div
          className={`text-xs text-gray-400 mb-1 ${side === "right" ? "text-right" : ""}`}
        >
          {label}
        </div>
      )}
      <div className="w-full bg-gray-800 rounded-full h-4 overflow-hidden">
        <div
          className={`h-full ${colorClass} transition-all duration-200 ${
            side === "right" ? "ml-auto" : ""
          }`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
