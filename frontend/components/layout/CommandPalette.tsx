"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { usePaletteStore } from "@/store/palette";

export function CommandPalette() {
  const { open, setOpen, assets } = usePaletteStore();
  const [query, setQuery] = useState("");
  const router = useRouter();

  const filtered = assets.filter(
    (a) =>
      a.symbol.toLowerCase().includes(query.toLowerCase()) ||
      a.name.toLowerCase().includes(query.toLowerCase()),
  );

  const hasMatches = filtered.length > 0;

  function handleSelect(symbol: string) {
    router.push(`/portfolio/${symbol}`);
    setOpen(false);
    setQuery("");
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
        placeholder="Search holdings..."
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        {hasMatches ? (
          <CommandGroup heading="Holdings">
            {filtered.map((asset) => (
              <CommandItem
                key={asset.id}
                onSelect={() => handleSelect(asset.symbol)}
                className="flex items-center gap-2"
              >
                <span className="font-mono font-medium">{asset.symbol}</span>
                <span className="text-muted-foreground text-sm">{asset.name}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        ) : (
          <CommandEmpty>
            <span>No holdings match &ldquo;{query}&rdquo;</span>
          </CommandEmpty>
        )}

        {!hasMatches && query.length > 0 && (
          <CommandGroup heading="AI">
            <CommandItem
              disabled
              className="opacity-40 cursor-not-allowed select-none"
              title="AI analysis available once LLM is configured (Phase 6)"
            >
              <span className="text-muted-foreground">
                Ask AI: &ldquo;{query}&rdquo;
              </span>
            </CommandItem>
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  );
}
