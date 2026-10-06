'use client';

import React, { useEffect, useState, useRef } from 'react';

interface LatencyClockProps {
  isPending: boolean;
  serverLatencyMs?: number;
}

export function LatencyClock({ isPending, serverLatencyMs }: LatencyClockProps) {
  const [elapsed, setElapsed] = useState<number>(0);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const startTimeRef = useRef<number>(0);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
      setPrefersReducedMotion(mediaQuery.matches);

      const handler = (e: MediaQueryListEvent) => {
        setPrefersReducedMotion(e.matches);
      };
      mediaQuery.addEventListener('change', handler);
      return () => mediaQuery.removeEventListener('change', handler);
    }
  }, []);

  useEffect(() => {
    if (isPending) {
      startTimeRef.current = performance.now();
      if (prefersReducedMotion) {
        return;
      }
      const interval = setInterval(() => {
        const diff = Math.floor(performance.now() - startTimeRef.current);
        // Round to 10ms steps
        setElapsed(Math.floor(diff / 10) * 10);
      }, 10);

      return () => clearInterval(interval);
    }
  }, [isPending, prefersReducedMotion]);

  if (isPending) {
    return (
      <div
        data-testid="latency-clock"
        data-latency-frozen="false"
        aria-live="off"
        className="flex items-baseline gap-2 font-mono text-ink tabular-nums"
      >
        <span
          className="inline-block w-2.5 h-2.5 rounded-full bg-ink/40 animate-pulse self-center"
          aria-hidden="true"
        />
        <span data-testid="latency-val" className="text-[32px] leading-[36px] font-semibold">
          {prefersReducedMotion ? '…' : `${elapsed}`}
        </span>
        <span className="text-ink-2 font-normal text-base">ms (đang chạy)</span>
      </div>
    );
  }

  const finalValue =
    typeof serverLatencyMs === 'number'
      ? Math.round(serverLatencyMs)
      : 0;

  return (
    <div
      data-testid="latency-clock"
      data-latency-frozen="true"
      aria-live="polite"
      className="flex items-baseline gap-1 font-mono tabular-nums text-ink font-semibold"
    >
      <span data-testid="latency-val" className="text-[32px] leading-[36px]">
        {finalValue}
      </span>
      <span className="text-ink-2 font-normal text-base">ms</span>
    </div>
  );
}
