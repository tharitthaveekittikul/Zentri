"use client";

import { useRef, useState, useEffect } from "react";
import { Eye, EyeOff, LogOut, Sun, Moon, Search } from "lucide-react";
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
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

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

    (
      document as Document & {
        startViewTransition: (cb: () => void | Promise<void>) => void;
      }
    ).startViewTransition(() => setTheme(newTheme));
  }

  return (
    <header className="bg-transparent pt-4 px-4 shrink-0">
      {/* Card wrapper — mirrors the sidebar card */}
      <div className="bg-white dark:bg-slate-900 rounded-[24px] border border-slate-200/60 dark:border-slate-800 flex items-center px-5 h-16 gap-3">
        {/* Search pill — tinted so it reads against the white card */}
        <button
          onClick={() => setOpen(true)}
          className="flex flex-1 items-center gap-3 h-10 px-4 rounded-full bg-slate-100/70 dark:bg-slate-800 border border-slate-200/60 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-left min-w-0"
          title="Search (⌘K)"
        >
          <Search
            className="h-[15px] w-[15px] text-slate-400 shrink-0"
            strokeWidth={1.5}
          />
          <span className="text-sm text-slate-400 flex-1 truncate">
            Search assets, pages...
          </span>
          <kbd className="hidden sm:flex items-center text-[11px] text-slate-400/60 font-mono bg-white dark:bg-slate-700 px-1.5 py-0.5 rounded-md border border-slate-200/60 dark:border-slate-600 shrink-0">
            ⌘K
          </kbd>
        </button>

        {/* Action buttons */}
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 shrink-0 rounded-full"
          onClick={toggle}
          title="Toggle privacy mode"
        >
          {isPrivate ? (
            <EyeOff className="h-[17px] w-[17px]" strokeWidth={1.5} />
          ) : (
            <Eye className="h-[17px] w-[17px]" strokeWidth={1.5} />
          )}
        </Button>
        <Button
          ref={toggleRef}
          variant="ghost"
          size="icon"
          className="h-9 w-9 shrink-0 relative rounded-full"
          onClick={toggleTheme}
          title={
            mounted && resolvedTheme === "dark"
              ? "Switch to light mode"
              : "Switch to dark mode"
          }
        >
          <span
            key={mounted ? resolvedTheme : "init"}
            style={{
              animation: mounted
                ? "icon-spin-in 300ms cubic-bezier(0.16,1,0.3,1) both"
                : undefined,
              display: "flex",
            }}
          >
            {mounted && resolvedTheme === "dark" ? (
              <Sun className="h-[17px] w-[17px]" strokeWidth={1.5} />
            ) : (
              <Moon className="h-[17px] w-[17px]" strokeWidth={1.5} />
            )}
          </span>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 shrink-0 rounded-full"
          onClick={handleLogout}
          title="Log out"
        >
          <LogOut className="h-[17px] w-[17px]" strokeWidth={1.5} />
        </Button>
      </div>
    </header>
  );
}
