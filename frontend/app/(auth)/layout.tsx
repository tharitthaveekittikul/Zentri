"use client";

import { useEffect } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopNav } from "@/components/layout/TopNav";
import { BottomTabBar } from "@/components/layout/BottomTabBar";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { usePaletteStore } from "@/store/palette";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const setOpen = usePaletteStore((s) => s.setOpen);
  const loadAssets = usePaletteStore((s) => s.loadAssets);

  useEffect(() => {
    loadAssets();
  }, [loadAssets]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(true);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [setOpen]);

  return (
    <div className="flex h-screen bg-page dark:bg-page">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopNav />
        <main className="flex-1 overflow-hidden pt-3 px-3">
          <div className="overflow-auto h-full p-6 md:p-8 pb-safe-tab bg-shell dark:bg-shell rounded-t-[28px] [will-change:transform]">
            {children}
          </div>
        </main>
      </div>
      <BottomTabBar />
      <CommandPalette />
    </div>
  );
}
