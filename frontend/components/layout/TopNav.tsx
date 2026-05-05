"use client";

import { useRef } from "react";
import { Eye, EyeOff, LogOut, Search, Sun, Moon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePrivacyStore } from "@/store/privacy";
import { usePaletteStore } from "@/store/palette";
import { logout } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";

export function TopNav() {
  const { isPrivate, toggle } = usePrivacyStore();
  const { setOpen } = usePaletteStore();
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  const toggleRef = useRef<HTMLButtonElement>(null);

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  function toggleTheme() {
    if (!resolvedTheme) return;
    const newTheme = resolvedTheme === "dark" ? "light" : "dark";
    const btn = toggleRef.current;
    const rect = btn?.getBoundingClientRect();
    const x = rect ? rect.left + rect.width / 2 : window.innerWidth / 2;
    const y = rect ? rect.top + rect.height / 2 : window.innerHeight / 2;

    document.documentElement.style.setProperty("--vt-x", `${x}px`);
    document.documentElement.style.setProperty("--vt-y", `${y}px`);

    if (!("startViewTransition" in document)) {
      setTheme(newTheme);
      return;
    }

    (document as Document & { startViewTransition: (cb: () => void | Promise<void>) => void })
      .startViewTransition(() => setTheme(newTheme));
  }

  return (
    <header className="h-14 border-b border-[var(--glass-border)] glass-chrome flex items-center justify-end px-4 gap-1">
      <Button variant="ghost" size="icon" onClick={() => setOpen(true)} title="Search (⌘K)">
        <Search className="h-4 w-4" />
      </Button>
      <Button variant="ghost" size="icon" onClick={toggle} title="Toggle privacy mode">
        {isPrivate ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </Button>
      <Button
        ref={toggleRef}
        variant="ghost"
        size="icon"
        onClick={toggleTheme}
        title={resolvedTheme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        className="relative"
      >
        <span
          key={resolvedTheme}
          style={{
            animation: "icon-spin-in 300ms cubic-bezier(0.16,1,0.3,1) both",
            display: "flex",
          }}
        >
          {resolvedTheme === "dark" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </span>
      </Button>
      <Button variant="ghost" size="icon" onClick={handleLogout} title="Log out">
        <LogOut className="h-4 w-4" />
      </Button>
    </header>
  );
}
