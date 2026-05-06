"use client";

import { useRef } from "react";
import { usePathname } from "next/navigation";
import { Eye, EyeOff, LogOut, Search, Sun, Moon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePrivacyStore } from "@/store/privacy";
import { usePaletteStore } from "@/store/palette";
import { logout } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";

const PAGE_TITLES: Record<string, string> = {
  "/": "Overview",
  "/portfolio": "Portfolio",
  "/watchlist": "Watchlist",
  "/net-worth": "Net Worth",
  "/dividends": "Dividends",
  "/transactions": "Transactions",
  "/documents": "Documents",
  "/pipeline": "Pipeline",
  "/import": "Import",
  "/ai-usage": "AI Usage",
  "/settings": "Settings",
  "/settings/ai": "AI & LLM",
  "/settings/backup": "Backup",
};

function resolveTitle(pathname: string): string {
  if (PAGE_TITLES[pathname]) return PAGE_TITLES[pathname];
  if (pathname.startsWith("/portfolio/")) return "Asset";
  return "Zentri";
}

export function TopNav() {
  const { isPrivate, toggle } = usePrivacyStore();
  const { setOpen } = usePaletteStore();
  const router = useRouter();
  const pathname = usePathname();
  const { resolvedTheme, setTheme } = useTheme();
  const toggleRef = useRef<HTMLButtonElement>(null);

  const pageTitle = resolveTitle(pathname);

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
    <header className="h-14 border-b border-[var(--glass-border)] glass-chrome flex items-center px-3 gap-0.5 md:gap-1 relative">
      {/* Mobile only: centered iOS-style page title — fades in on route change */}
      <div className="md:hidden absolute inset-x-0 flex justify-center pointer-events-none">
        <span
          key={pathname}
          className="text-[17px] font-bold tracking-[-0.01em]"
          style={{ animation: "nav-title-in 280ms cubic-bezier(0.22, 1, 0.36, 1) both" }}
        >
          {pageTitle}
        </span>
      </div>

      {/* Desktop: wordmark on left */}
      <span className="hidden md:block text-sm font-semibold tracking-widest uppercase text-foreground/80 mr-auto">
        Zentri
      </span>

      {/* Mobile spacer — pushes actions to right */}
      <div className="flex-1 md:hidden" />

      <Button variant="ghost" size="icon" className="h-9 w-9" onClick={() => setOpen(true)} title="Search (⌘K)">
        <Search className="h-[18px] w-[18px]" />
      </Button>
      <Button variant="ghost" size="icon" className="h-9 w-9" onClick={toggle} title="Toggle privacy mode">
        {isPrivate ? <EyeOff className="h-[18px] w-[18px]" /> : <Eye className="h-[18px] w-[18px]" />}
      </Button>
      <Button
        ref={toggleRef}
        variant="ghost"
        size="icon"
        className="h-9 w-9 relative"
        onClick={toggleTheme}
        title={resolvedTheme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      >
        <span
          key={resolvedTheme}
          style={{
            animation: "icon-spin-in 300ms cubic-bezier(0.16,1,0.3,1) both",
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
      <Button variant="ghost" size="icon" className="h-9 w-9" onClick={handleLogout} title="Log out">
        <LogOut className="h-[18px] w-[18px]" />
      </Button>
    </header>
  );
}
