"use client";

import { useUiStore } from "@/stores/uiStore";

export function CrtOverlay() {
  const crtEnabled = useUiStore((s) => s.crtEnabled);

  if (!crtEnabled) return null;

  return <div className="crt-overlay" aria-hidden="true" />;
}
