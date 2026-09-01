// Mobile bottom sheet — Google Maps / Uber style. Web-only (raw DOM +
// touch/mouse events, not React Native gesture primitives) since this is
// only ever mounted from index.web.tsx's mobile branch; the map behind it
// stays full-bleed and interactive at every snap state except 'full'.
//
// Deliberately NOT using the Pointer Events API / setPointerCapture: iOS
// WebKit's implementation is unreliable enough that a capture which fails
// to release cleanly ends up swallowing touches for the rest of the sheet
// (confirmed on a real iPhone — every Pressable inside the sheet stopped
// responding to touch, while everything outside it, e.g. the top-right
// account menu, kept working fine). Touch events don't need capture at all
// — the spec guarantees touchmove/touchend keep firing on the element
// touchstart began on — and mouse dragging uses a standard document-level
// listener pair instead.
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

  const startDrag = (clientY: number) => {
    draggingRef.current = true;
    startYRef.current = clientY;
    startHeightRef.current = snapHeight(snap);
  };
  const moveDrag = (clientY: number) => {
    if (!draggingRef.current) return;
    // Positive delta = finger/cursor moved down = shrink the sheet.
    setDragDelta(clientY - startYRef.current);
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

  // React Native Web installs a document-level touch tracker (feeds its
  // Pressable/responder system) that listens to every touch on the page
  // regardless of React's own event propagation. The grip's touches are
  // handled entirely by this component and were never meant to enter that
  // system — left alone, they desync its internal touch-id bookkeeping
  // ("Cannot find single active touch") and that corrupted state then
  // breaks Pressables elsewhere on the page, not just here. Stopping the
  // native event outright (not just React's synthetic one) keeps the grip's
  // drag fully local.
  const isolate = (e: { nativeEvent: Event }) => e.nativeEvent.stopImmediatePropagation();

  // Touch: touchmove/touchend are guaranteed by spec to keep firing on the
  // element touchstart began on, wherever the finger goes — no capture API
  // needed, so these can just be plain React props on the grip.
  const onGripTouchStart = (e: React.TouchEvent) => { isolate(e); startDrag(e.touches[0].clientY); };
  const onGripTouchMove = (e: React.TouchEvent) => { isolate(e); moveDrag(e.touches[0].clientY); };
  const onGripTouchEnd = (e: React.TouchEvent) => { isolate(e); endDrag(); };

  // Mouse: unlike touch, mousemove/mouseup don't keep targeting the
  // original element once the cursor leaves it, so drag tracking needs
  // document-level listeners — the standard pattern, attached on mousedown
  // and torn down on mouseup so nothing lingers between drags.
  const onGripMouseDown = (e: React.MouseEvent) => {
    isolate(e);
    startDrag(e.clientY);
    const onMove = (ev: MouseEvent) => moveDrag(ev.clientY);
    const onUp = () => {
      endDrag();
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
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
        onTouchStart={onGripTouchStart}
        onTouchMove={onGripTouchMove}
        onTouchEnd={onGripTouchEnd}
        onTouchCancel={onGripTouchEnd}
        onMouseDown={onGripMouseDown}
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
