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

function NavItem({
  href,
  label,
  icon: Icon,
  pathname,
}: {
  href: string;
  label: string;
  icon: React.ElementType;
  pathname: string;
}) {
  const isActive = pathname === href;
  return (
    <div className="relative">
      {isActive && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-emerald-600 rounded-full" />
      )}
      <Link
        href={href}
        className={cn(
          "mx-3 flex items-center gap-3 px-3 py-2.5 rounded-full text-[15px] tracking-wide transition-colors duration-150",
          isActive
            ? "bg-emerald-100/60 dark:bg-emerald-950/20 text-emerald-900 dark:text-emerald-100 font-bold"
            : "text-slate-500 dark:text-slate-400 font-normal hover:text-slate-700 dark:hover:text-slate-300",
        )}
      >
        <Icon className="h-[18px] w-[18px] shrink-0" strokeWidth={1.2} />
        {label}
      </Link>
    </div>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden md:flex w-72 flex-col h-full py-4 pl-4">
      {/* Single card wrapping logo + nav */}
      <div className="flex-1 bg-white dark:bg-slate-900 rounded-[24px] border border-slate-200/60 dark:border-slate-800 flex flex-col overflow-hidden">
        {/* Logo area */}
        <div className="flex items-center gap-4 px-5 h-20 shrink-0">
          <div
            className="flex items-center justify-center w-11 h-11 rounded-2xl bg-slate-900 dark:bg-white shrink-0"
            aria-hidden="true"
          >
            <svg
              width="22"
              height="22"
              viewBox="0 0 14 14"
              fill="none"
              className="text-white dark:text-slate-900"
            >
              <path
                d="M2 2.5h10L5.5 7.5H12M2 11.5h10"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <span className="text-base font-semibold tracking-[0.06em] uppercase text-slate-900 dark:text-white leading-none">
            Zentri
          </span>
        </div>

        <div className="mx-4 h-px bg-slate-100 dark:bg-slate-800 shrink-0" />

        <nav className="flex-1 flex flex-col py-4 overflow-y-auto">
          <p className="px-5 mb-2 text-[10px] font-semibold tracking-[0.12em] uppercase text-slate-400/70 dark:text-slate-500">
            Portfolio
          </p>
          <div className="flex flex-col gap-1.5">
            {mainNavItems.map((item) => (
              <NavItem key={item.href} {...item} pathname={pathname} />
            ))}
          </div>

          <div className="my-4 mx-4 h-px bg-slate-100 dark:bg-slate-800" />

          <p className="px-5 mb-2 text-[10px] font-semibold tracking-[0.12em] uppercase text-slate-400/70 dark:text-slate-500">
            Tools
          </p>
          <div className="flex flex-col gap-1.5">
            {toolNavItems.map((item) => (
              <NavItem key={item.href} {...item} pathname={pathname} />
            ))}
          </div>
        </nav>
      </div>
    </aside>
  );
}
