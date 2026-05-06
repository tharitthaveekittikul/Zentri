"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Briefcase,
  Star,
  TrendingUp,
  CalendarDays,
  Receipt,
  FileText,
  Activity,
  Bot,
  Settings,
  Upload,
  HardDrive,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/watchlist", label: "Watchlist", icon: Star },
  { href: "/net-worth", label: "Net Worth", icon: TrendingUp },
  { href: "/events", label: "Events", icon: CalendarDays },
  { href: "/transactions", label: "Transactions", icon: Receipt },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/pipeline", label: "Pipeline", icon: Activity },
  { href: "/import", label: "Import", icon: Upload },
  { href: "/ai-usage", label: "AI Usage", icon: Bot },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/settings/backup", label: "Backup", icon: HardDrive },
];

const mainNavItems = navItems.slice(0, 5);
const toolNavItems = navItems.slice(5);

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden md:flex w-56 border-r border-sidebar-border glass-chrome flex-col py-4 h-full">
      <div className="px-5 mb-5">
        <span className="text-sm font-semibold tracking-widest uppercase text-foreground">Zentri</span>
      </div>
      <nav className="flex-1 flex flex-col gap-0.5 px-2">
        {mainNavItems.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-all duration-150",
                isActive
                  ? "bg-sidebar-primary text-sidebar-primary-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0",
                  isActive ? "opacity-100" : "opacity-70"
                )}
              />
              {label}
            </Link>
          );
        })}

        <div className="my-3 mx-3 h-px bg-border/50" />

        {toolNavItems.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-all duration-150",
                isActive
                  ? "bg-sidebar-primary text-sidebar-primary-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0",
                  isActive ? "opacity-100" : "opacity-70"
                )}
              />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
