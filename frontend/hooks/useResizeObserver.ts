import { useEffect, useRef, useState } from "react";

export function useResizeObserver<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const update = (w: number, h: number) => {
      if (w > 0 && h > 0) setSize({ width: w, height: h });
    };

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) update(entry.contentRect.width, entry.contentRect.height);
    });

    observer.observe(el);
    const rect = el.getBoundingClientRect();
    update(rect.width, rect.height);

    return () => observer.disconnect();
  }, []);

  return { ref, width: size.width, height: size.height };
}
