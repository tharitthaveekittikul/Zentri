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
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopNav />
        <main className="flex-1 overflow-auto p-4 md:p-6 pb-safe-tab md:pb-6 bg-background">
          {children}
        </main>
      </div>
      <BottomTabBar />
      <CommandPalette />
    </div>
  );
}
