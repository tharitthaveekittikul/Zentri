"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Briefcase,
  Star,
  TrendingUp,
  Settings,
} from "lucide-react";

const tabs = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/watchlist", label: "Watchlist", icon: Star },
  { href: "/net-worth", label: "Net Worth", icon: TrendingUp },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function BottomTabBar() {
  const pathname = usePathname();

  return (
    <nav
      className="md:hidden fixed z-50 left-3 right-3"
      style={{ bottom: "calc(14px + env(safe-area-inset-bottom))" }}
    >
      <div
        className="glass-chrome rounded-[26px] border border-[var(--glass-border)] overflow-hidden"
        style={{
          boxShadow:
            "0 8px 48px oklch(0 0 0 / 18%), 0 2px 16px oklch(0 0 0 / 10%), inset 0 1px 0 var(--glass-specular)",
        }}
      >
        <div className="flex items-center h-[62px] px-1">
          {tabs.map(({ href, label, icon: Icon }) => {
            const isActive =
              href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex-1 flex flex-col items-center justify-center gap-[3px]",
                  "rounded-[20px] h-[54px] transition-all duration-200 active:scale-[0.93]",
                  isActive ? "text-foreground" : "text-muted-foreground"
                )}
              >
                {/* Icon with active fill */}
                <div
                  className={cn(
                    "flex items-center justify-center w-9 h-[26px] rounded-[10px]",
                    "transition-all duration-200",
                    isActive ? "bg-foreground/[0.09]" : ""
                  )}
                >
                  <Icon
                    className="h-[20px] w-[20px] transition-all duration-150"
                    strokeWidth={isActive ? 2.25 : 1.5}
                  />
                </div>
                {/* Label */}
                <span
                  className={cn(
                    "text-[10px] leading-none tracking-[0.01em] transition-all duration-150",
                    isActive ? "font-semibold opacity-100" : "font-medium opacity-50"
                  )}
                >
                  {label}
                </span>
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
