"use client";

import { useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export function useTableParams() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const get = useCallback(
    (key: string, fallback = "") => searchParams.get(key) ?? fallback,
    [searchParams],
  );

  const getInt = useCallback(
    (key: string, fallback: number) =>
      Number(searchParams.get(key) || fallback),
    [searchParams],
  );

  const setParam = useCallback(
    (
      updates: Record<string, string | number | null>,
      resetPage = true,
    ) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === "") {
          params.delete(key);
        } else {
          params.set(key, String(value));
        }
      }
      if (resetPage && !("page" in updates)) {
        params.set("page", "1");
      }
      router.replace(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  return { get, getInt, setParam };
}
