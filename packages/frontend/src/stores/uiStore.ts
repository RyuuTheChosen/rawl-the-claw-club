import { create } from "zustand";

interface UiState {
  crtEnabled: boolean;
  toggleCrt: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  crtEnabled:
    typeof window !== "undefined"
      ? localStorage.getItem("rawl_crt") !== "false"
      : true,
  toggleCrt: () =>
    set((state) => {
      const next = !state.crtEnabled;
      if (typeof window !== "undefined") {
        localStorage.setItem("rawl_crt", String(next));
      }
      return { crtEnabled: next };
    }),
}));
