import { create } from "zustand";

interface WalletState {
  apiKey: string | null;
  walletAddress: string | null;
  connected: boolean;
  setApiKey: (key: string | null) => void;
  setWalletAddress: (addr: string | null) => void;
  setConnected: (connected: boolean) => void;
  logout: () => void;
}

export const useWalletStore = create<WalletState>((set) => ({
  apiKey: typeof window !== "undefined" ? localStorage.getItem("rawl_api_key") : null,
  walletAddress: typeof window !== "undefined" ? localStorage.getItem("rawl_wallet") : null,
  connected: false,
  setApiKey: (key) => {
    if (key) {
      localStorage.setItem("rawl_api_key", key);
    } else {
      localStorage.removeItem("rawl_api_key");
    }
    set({ apiKey: key });
  },
  setWalletAddress: (addr) => {
    if (addr) {
      localStorage.setItem("rawl_wallet", addr);
    } else {
      localStorage.removeItem("rawl_wallet");
    }
    set({ walletAddress: addr });
  },
  setConnected: (connected) => set({ connected }),
  logout: () => {
    localStorage.removeItem("rawl_api_key");
    localStorage.removeItem("rawl_wallet");
    set({ apiKey: null, walletAddress: null, connected: false });
  },
}));
