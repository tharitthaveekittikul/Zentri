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
  FileText,
  Activity,
  Bot,
  Settings,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/watchlist", label: "Watchlist", icon: Star },
  { href: "/net-worth", label: "Net Worth", icon: TrendingUp },
  { href: "/dividends", label: "Dividends", icon: CalendarDays },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/pipeline", label: "Pipeline", icon: Activity },
  { href: "/ai-usage", label: "AI Usage", icon: Bot },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-56 border-r bg-card flex flex-col py-4">
      <div className="px-4 mb-6">
        <span className="font-bold text-lg">Zentri</span>
      </div>
      <nav className="flex-1 space-y-1 px-2">
        {navItems.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors",
              pathname === href
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
