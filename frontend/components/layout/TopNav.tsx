"use client";

import { Eye, EyeOff, LogOut, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePrivacyStore } from "@/store/privacy";
import { usePaletteStore } from "@/store/palette";
import { logout } from "@/lib/auth";
import { useRouter } from "next/navigation";

export function TopNav() {
  const { isPrivate, toggle } = usePrivacyStore();
  const { setOpen } = usePaletteStore();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <header className="h-14 border-b flex items-center justify-end px-4 gap-2 bg-card">
      <Button variant="ghost" size="icon" onClick={() => setOpen(true)} title="Search (⌘K)">
        <Search className="h-4 w-4" />
      </Button>
      <Button variant="ghost" size="icon" onClick={toggle} title="Toggle privacy mode">
        {isPrivate ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </Button>
      <Button variant="ghost" size="icon" onClick={handleLogout} title="Log out">
        <LogOut className="h-4 w-4" />
      </Button>
    </header>
  );
}
