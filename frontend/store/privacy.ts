import { create } from "zustand";
import { persist } from "zustand/middleware";

interface PrivacyState {
  isPrivate: boolean;
  toggle: () => void;
  setPrivate: (value: boolean) => void;
}

export const usePrivacyStore = create<PrivacyState>()(
  persist(
    (set) => ({
      isPrivate: false,
      toggle: () => set((state) => ({ isPrivate: !state.isPrivate })),
      setPrivate: (value: boolean) => set({ isPrivate: value }),
    }),
    { name: "zentri-privacy" }
  )
);
