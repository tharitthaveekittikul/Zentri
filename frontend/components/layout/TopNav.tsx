"use client";

import { useRef } from "react";
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
    <header className="h-14 border-b border-[var(--glass-border)] glass-chrome flex items-center px-3 gap-2">
      {/* Search pill */}
      <button
        onClick={() => setOpen(true)}
        className="flex flex-1 items-center gap-2 h-9 px-3 rounded-full bg-muted/60 hover:bg-muted transition-colors text-left min-w-0"
        title="Search (⌘K)"
      >
        <Search className="h-[15px] w-[15px] text-muted-foreground shrink-0" />
        <span className="text-sm text-muted-foreground flex-1 truncate">
          Search...
        </span>
        <kbd className="hidden sm:flex items-center text-[11px] text-muted-foreground/60 font-mono bg-background/60 px-1.5 py-0.5 rounded-md border border-border/40 shrink-0">
          ⌘K
        </kbd>
      </button>

      {/* Action buttons */}
      <Button
        variant="ghost"
        size="icon"
        className="h-9 w-9 shrink-0"
        onClick={toggle}
        title="Toggle privacy mode"
      >
        {isPrivate ? (
          <EyeOff className="h-[18px] w-[18px]" />
        ) : (
          <Eye className="h-[18px] w-[18px]" />
        )}
      </Button>
      <Button
        ref={toggleRef}
        variant="ghost"
        size="icon"
        className="h-9 w-9 shrink-0 relative"
        onClick={toggleTheme}
        title={
          resolvedTheme === "dark"
            ? "Switch to light mode"
            : "Switch to dark mode"
        }
      >
        <span
          key={resolvedTheme}
          style={{
            animation: "icon-spin-in 1500ms cubic-bezier(0.16,1,0.3,1) both",
            display: "flex",
          }}
        >
          {resolvedTheme === "dark" ? (
            <Sun className="h-[18px] w-[18px]" />
          ) : (
            <Moon className="h-[18px] w-[18px]" />
          )}
        </span>
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="h-9 w-9 shrink-0"
        onClick={handleLogout}
        title="Log out"
      >
        <LogOut className="h-[18px] w-[18px]" />
      </Button>
    </header>
  );
}
