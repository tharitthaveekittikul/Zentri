"use client";

import Image from "next/image";
import { useState } from "react";

export function TickerLogo({
  symbol,
  logoUrl,
  size = 24,
}: {
  symbol: string;
  logoUrl?: string;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);

  if (!logoUrl || failed) return null;

  return (
    <Image
      src={logoUrl}
      alt={symbol}
      width={size}
      height={size}
      unoptimized
      loading="lazy"
      className="rounded-full object-contain shrink-0"
      onError={() => setFailed(true)}
    />
  );
}
