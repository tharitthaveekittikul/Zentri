"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LayoutDashboard } from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { usePaletteStore } from "@/store/palette";
import { PAGES, type PageEntry } from "@/lib/search/pages";

export function CommandPalette() {
  const { open, setOpen, assets } = usePaletteStore();
  const [query, setQuery] = useState("");
  const router = useRouter();

  const q = query.toLowerCase();

  const filteredPages = q
    ? PAGES.filter(
        (p) =>
          p.label.toLowerCase().includes(q) ||
          p.keywords.some((k) => k.toLowerCase().includes(q)),
      )
    : PAGES;

  const filteredAssets = q
    ? assets.filter(
        (a) =>
          a.symbol.toLowerCase().includes(q) ||
          a.name.toLowerCase().includes(q),
      )
    : assets;

  const hasPages = filteredPages.length > 0;
  const hasAssets = filteredAssets.length > 0;

  function handleSelectPage(entry: PageEntry) {
    router.push(entry.url);
    setOpen(false);
    setQuery("");
  }

  function handleSelectAsset(symbol: string) {
    router.push(`/portfolio/${symbol}`);
    setOpen(false);
    setQuery("");
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
        placeholder="Search pages or holdings..."
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        {q && !hasPages && !hasAssets && (
          <CommandEmpty>No results for &ldquo;{query}&rdquo;</CommandEmpty>
        )}
        {!q && !hasPages && !hasAssets && (
          <CommandEmpty>No pages found.</CommandEmpty>
        )}

        {hasPages && (
          <CommandGroup heading="Pages">
            {filteredPages.map((entry) => (
              <CommandItem
                key={entry.url}
                value={`${entry.label} ${entry.keywords.join(" ")}`}
                onSelect={() => handleSelectPage(entry)}
                className="flex items-center gap-2"
              >
                <LayoutDashboard className="h-4 w-4 text-muted-foreground shrink-0" />
                <span>{entry.label}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}

        {hasAssets && (
          <CommandGroup heading="Holdings">
            {filteredAssets.map((asset) => (
              <CommandItem
                key={asset.id}
                onSelect={() => handleSelectAsset(asset.symbol)}
                className="flex items-center gap-2"
              >
                <span className="font-mono font-medium">{asset.symbol}</span>
                <span className="text-muted-foreground text-sm">{asset.name}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  );
}
