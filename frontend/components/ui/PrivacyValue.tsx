"use client";

import { ReactNode } from "react";
import { usePrivacyStore } from "@/store/privacy";
import { cn } from "@/lib/utils";

interface Props {
  value: string | ReactNode;
  className?: string;
}

export function PrivacyValue({ value, className }: Props) {
  const { isPrivate } = usePrivacyStore();
  return <span className={cn(className)}>{isPrivate ? "******" : value}</span>;
}
