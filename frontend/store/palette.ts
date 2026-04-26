import { create } from "zustand";
import { Asset, fetchAllAssets } from "@/lib/services/assets";

interface PaletteState {
  open: boolean;
  assets: Asset[];
  setOpen: (open: boolean) => void;
  loadAssets: () => Promise<void>;
}

export const usePaletteStore = create<PaletteState>((set) => ({
  open: false,
  assets: [],
  setOpen: (open) => set({ open }),
  loadAssets: async () => {
    try {
      const assets = await fetchAllAssets();
      set({ assets });
    } catch {
      // palette degrades gracefully
    }
  },
}));
