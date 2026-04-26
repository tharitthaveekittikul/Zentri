import { create } from "zustand";
import { persist } from "zustand/middleware";

interface PrivacyState {
  isPrivate: boolean;
  toggle: () => void;
}

export const usePrivacyStore = create<PrivacyState>()(
  persist(
    (set) => ({
      isPrivate: false,
      toggle: () => set((state) => ({ isPrivate: !state.isPrivate })),
    }),
    { name: "zentri-privacy" }
  )
);
