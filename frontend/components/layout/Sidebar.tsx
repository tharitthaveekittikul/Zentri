"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Briefcase,
  PieChart,
  Star,
  TrendingUp,
  CalendarDays,
  Receipt,
  Activity,
  Bot,
  MessageSquare,
  Settings,
  Upload,
  HardDrive,
  BarChart2,
} from "lucide-react";

const navItems = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/allocation", label: "Allocation", icon: PieChart },
  { href: "/watchlist", label: "Watchlist", icon: Star },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/net-worth", label: "Net Worth", icon: TrendingUp },
  { href: "/events", label: "Events", icon: CalendarDays },
  { href: "/transactions", label: "Transactions", icon: Receipt },
  { href: "/pipeline", label: "Pipeline", icon: Activity },
  { href: "/import", label: "Import", icon: Upload },
  { href: "/analysis", label: "Analysis", icon: BarChart2 },
  { href: "/ai-usage", label: "AI Usage", icon: Bot },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/settings/backup", label: "Backup", icon: HardDrive },
];

const mainNavItems = navItems.slice(0, 6);
const toolNavItems = navItems.slice(6);

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
      <span
        className="absolute left-0 top-1/2 w-[3px] h-5 rounded-full"
        style={{
          background: 'var(--gradient-brand)',
          transform: `translateY(-50%) scaleY(${isActive ? 1 : 0})`,
          transformOrigin: 'center',
          transition: 'transform 200ms var(--motion-spring)',
        }}
      />
      <Link
        href={href}
        className={cn(
          "mx-3 flex items-center gap-3 px-3 py-2.5 rounded-full text-[15px] tracking-wide transition-colors duration-150",
          isActive
            ? "bg-brand-accent/10 dark:bg-brand-accent/15 text-brand-deep dark:text-brand-sage font-semibold"
            : "text-ink-muted/60 dark:text-ink-muted/60 font-normal hover:text-ink dark:hover:text-ink",
        )}
        style={{ transition: 'color 150ms ease, background-color 150ms ease' }}
      >
        <Icon
          className="h-[18px] w-[18px] shrink-0"
          strokeWidth={1.2}
          style={{
            transition: 'transform 120ms var(--motion-spring)',
          }}
          onMouseEnter={(e: React.MouseEvent<SVGElement>) => { (e.currentTarget as SVGElement).style.transform = 'scale(1.08)'; }}
          onMouseLeave={(e: React.MouseEvent<SVGElement>) => { (e.currentTarget as SVGElement).style.transform = 'scale(1)'; }}
        />
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
      <div
        className="flex-1 rounded-[24px] flex flex-col overflow-hidden"
        style={{
          background: 'var(--glass-bg)',
          backdropFilter: `blur(var(--glass-blur)) saturate(var(--glass-saturate))`,
          WebkitBackdropFilter: `blur(var(--glass-blur)) saturate(var(--glass-saturate))`,
          boxShadow: 'inset 0 1px 0 var(--glass-specular)',
          border: '1px solid var(--glass-border)',
        }}
      >
        <div className="flex items-center gap-3 px-5 h-20 shrink-0">
          <div
            className="shrink-0 rounded-[6px]"
            style={{
              width: 24,
              height: 24,
              background: 'var(--gradient-brand)',
            }}
          />
          <span className="text-base font-semibold tracking-[0.06em] uppercase text-brand-deep dark:text-brand-sage leading-none">
            Zentri
          </span>
        </div>

        <div className="mx-4 h-px bg-slate-200/70 dark:bg-slate-800 shrink-0" />

        <nav className="flex-1 flex flex-col py-4 overflow-y-auto">
          <p className="px-5 mb-2 text-[10px] font-semibold tracking-[0.12em] uppercase text-slate-400/80 dark:text-slate-400">
            Portfolio
          </p>
          <div className="flex flex-col gap-1.5">
            {mainNavItems.map((item) => (
              <NavItem key={item.href} {...item} pathname={pathname} />
            ))}
          </div>

          <div className="my-4 mx-4 h-px bg-slate-100 dark:bg-slate-800" />

          <p className="px-5 mb-2 text-[10px] font-semibold tracking-[0.12em] uppercase text-slate-400/80 dark:text-slate-400">
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
