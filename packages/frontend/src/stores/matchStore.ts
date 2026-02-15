import { create } from "zustand";
import type { Match, MatchDataMessage } from "@/types";

interface MatchState {
  matches: Match[];
  currentMatch: Match | null;
  liveData: MatchDataMessage | null;
  loading: boolean;
  error: string | null;

  setMatches: (matches: Match[]) => void;
  setCurrentMatch: (match: Match | null) => void;
  setLiveData: (data: MatchDataMessage | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useMatchStore = create<MatchState>((set) => ({
  matches: [],
  currentMatch: null,
  liveData: null,
  loading: false,
  error: null,

  setMatches: (matches) => set({ matches }),
  setCurrentMatch: (currentMatch) => set({ currentMatch }),
  setLiveData: (liveData) => set({ liveData }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
}));
