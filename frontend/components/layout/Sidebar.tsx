"use client";

import React from "react";
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
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
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

function NavItem({ href, label, icon: Icon, pathname }: { href: string; label: string; icon: React.ElementType; pathname: string }) {
  const isActive = pathname === href;
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2.5 px-3 py-2 rounded-[10px] text-sm font-medium transition-all duration-150",
        isActive
          ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-sm"
          : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
      )}
    >
      <Icon
        className={cn(
          "h-[15px] w-[15px] shrink-0",
          isActive ? "opacity-100" : "opacity-50"
        )}
      />
      {label}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden md:flex w-56 border-r border-sidebar-border glass-chrome flex-col h-full">
      {/* Logo area */}
      <div className="flex items-center gap-2.5 px-4 h-14 border-b border-sidebar-border/60">
        <div
          className="flex items-center justify-center w-7 h-7 rounded-[8px] bg-foreground shrink-0"
          aria-hidden="true"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="text-background">
            <path d="M2 2.5h10L5.5 7.5H12M2 11.5h10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <span className="text-[13px] font-semibold tracking-[0.06em] uppercase text-foreground/90 leading-none">
          Zentri
        </span>
      </div>

      <nav className="flex-1 flex flex-col px-2 py-3 overflow-y-auto">
        {/* Main section */}
        <p className="px-3 mb-1.5 text-[10px] font-semibold tracking-[0.12em] uppercase text-sidebar-foreground/40">
          Portfolio
        </p>
        <div className="flex flex-col gap-px">
          {mainNavItems.map((item) => (
            <NavItem key={item.href} {...item} pathname={pathname} />
          ))}
        </div>

        <div className="my-3 mx-1 h-px bg-sidebar-border/60" />

        {/* Tools section */}
        <p className="px-3 mb-1.5 text-[10px] font-semibold tracking-[0.12em] uppercase text-sidebar-foreground/40">
          Tools
        </p>
        <div className="flex flex-col gap-px">
          {toolNavItems.map((item) => (
            <NavItem key={item.href} {...item} pathname={pathname} />
          ))}
        </div>
      </nav>
    </aside>
  );
}
