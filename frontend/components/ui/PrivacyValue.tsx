"use client";

import { usePrivacyStore } from "@/store/privacy";
import { cn } from "@/lib/utils";

interface Props {
  value: string;
  className?: string;
}

export function PrivacyValue({ value, className }: Props) {
  const { isPrivate } = usePrivacyStore();
  return <span className={cn(className)}>{isPrivate ? "••••" : value}</span>;
}
