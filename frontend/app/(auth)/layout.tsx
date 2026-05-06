"use client";

import { useEffect } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopNav } from "@/components/layout/TopNav";
import { BottomTabBar } from "@/components/layout/BottomTabBar";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { usePaletteStore } from "@/store/palette";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { setOpen, loadAssets } = usePaletteStore();

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
    <div className="flex h-screen bg-[#F2F4F7] dark:bg-slate-950">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopNav />
        <main className="flex-1 overflow-hidden p-6">
          <div className="bg-white dark:bg-slate-900 rounded-[32px] h-full border border-slate-200/60 dark:border-slate-800 overflow-hidden">
            <div className="overflow-auto h-full p-6 md:p-8 pb-safe-tab">
              {children}
            </div>
          </div>
        </main>
      </div>
      <BottomTabBar />
      <CommandPalette />
    </div>
  );
}
