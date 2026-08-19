// Mobile bottom sheet — Google Maps / Uber style. Web-only (raw DOM +
// pointer events, not React Native gesture primitives) since this is only
// ever mounted from index.web.tsx's mobile branch; the map behind it stays
// full-bleed and interactive at every snap state except 'full'.
import React, { useRef, useState } from 'react';

import { colors, radius } from '@/constants/theme';

export type SheetSnap = 'peek' | 'half' | 'full';

interface Props {
  snap: SheetSnap;
  onSnapChange: (snap: SheetSnap) => void;
  /** Height (px) of the collapsed state — just enough for a one-line
   *  summary, not full content. */
  peekHeight?: number;
  /** Always-visible content below the drag handle, at every snap state
   *  (e.g. a summary row + a couple of icon buttons). Its own Pressables
   *  work normally — only the handle strip above it captures drag/tap. */
  header?: React.ReactNode;
  children: React.ReactNode;
}

const HALF_FRACTION = 0.55;
const FULL_FRACTION = 0.92;
// Below this drag distance (px), a release is treated as a tap (cycle
// snap points) rather than a drag-to-nearest-snap.
const TAP_THRESHOLD_PX = 6;

export function BottomSheet({ snap, onSnapChange, peekHeight = 100, header, children }: Props) {
  const [dragDelta, setDragDelta] = useState(0);
  const draggingRef = useRef(false);
  const startYRef = useRef(0);
  const startHeightRef = useRef(0);

  const snapHeight = (s: SheetSnap): number => {
    const vh = typeof window !== 'undefined' ? window.innerHeight : 800;
    if (s === 'peek') return peekHeight;
    if (s === 'half') return Math.round(vh * HALF_FRACTION);
    return Math.round(vh * FULL_FRACTION);
  };

  const nearestSnap = (h: number): SheetSnap => {
    const options: [SheetSnap, number][] = [
      ['peek', snapHeight('peek')],
      ['half', snapHeight('half')],
      ['full', snapHeight('full')],
    ];
    let best = options[0];
    for (const opt of options) {
      if (Math.abs(opt[1] - h) < Math.abs(best[1] - h)) best = opt;
    }
    return best[0];
  };

  const currentHeight = Math.max(peekHeight, snapHeight(snap) - dragDelta);

  const onGripPointerDown = (e: React.PointerEvent) => {
    draggingRef.current = true;
    startYRef.current = e.clientY;
    startHeightRef.current = snapHeight(snap);
    // Pointer capture is a nice-to-have (keeps the drag tracking even if the
    // finger/cursor leaves the handle strip) — never worth crashing the
    // whole app over if the browser refuses it for some pointer edge case.
    try {
      (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    } catch {
      // ignore — drag still works without capture, just less forgiving
    }
  };
  const onGripPointerMove = (e: React.PointerEvent) => {
    if (!draggingRef.current) return;
    // Positive delta = finger moved down = shrink the sheet.
    setDragDelta(e.clientY - startYRef.current);
  };
  const endDrag = () => {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    const delta = dragDelta;
    setDragDelta(0);
    if (Math.abs(delta) < TAP_THRESHOLD_PX) {
      onSnapChange(snap === 'peek' ? 'half' : snap === 'half' ? 'full' : 'peek');
      return;
    }
    const next = nearestSnap(startHeightRef.current - delta);
    if (next !== snap) onSnapChange(next);
  };

  return (
    <div
      style={{
        position: 'fixed', left: 0, right: 0, bottom: 0,
        height: currentHeight,
        background: 'rgba(255,255,255,0.98)',
        backdropFilter: 'blur(6px)',
        borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg,
        boxShadow: '0 -4px 20px rgba(0,0,0,0.18)',
        zIndex: 40, display: 'flex', flexDirection: 'column',
        transition: draggingRef.current ? 'none' : 'height 0.22s ease',
      }}
    >
      <div
        onPointerDown={onGripPointerDown}
        onPointerMove={onGripPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        style={{
          flexShrink: 0, cursor: 'grab', paddingTop: 8, paddingBottom: 4,
          touchAction: 'none', userSelect: 'none',
        }}
      >
        <div style={{ width: 40, height: 5, borderRadius: 3, background: colors.border, margin: '0 auto' }} />
      </div>
      {header && <div style={{ flexShrink: 0 }}>{header}</div>}
      <div style={{ flex: 1, overflowY: 'auto', overscrollBehavior: 'contain', WebkitOverflowScrolling: 'touch', minHeight: 0 }}>
        {children}
      </div>
    </div>
  );
}
