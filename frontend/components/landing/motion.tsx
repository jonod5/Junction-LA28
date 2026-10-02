// Small motion kit for the landing page: entrance fades, scroll-triggered
// reveals, and a few looping accents. Everything renders static when the OS
// "reduce motion" setting is on.
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import {
  AccessibilityInfo,
  Animated,
  Easing,
  Platform,
  Text,
  type StyleProp,
  type TextStyle,
  useWindowDimensions,
  View,
  type ViewStyle,
} from 'react-native';

const NATIVE = Platform.OS !== 'web';
const EASE_OUT = Easing.bezier(0.2, 0.7, 0.2, 1);

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    AccessibilityInfo.isReduceMotionEnabled().then(setReduced).catch(() => {});
    const sub = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduced);
    return () => sub.remove();
  }, []);
  return reduced;
}

// ── Scroll reveal ──────────────────────────────────────────────────────────
// The page's ScrollView calls `check()` on scroll; each Reveal registers a
// callback that measures itself in the window and animates in once.

type Check = () => void;
const RevealContext = createContext<{ register: (fn: Check) => () => void } | null>(null);

export function useRevealHost() {
  const listeners = useRef(new Set<Check>());
  const register = useCallback((fn: Check) => {
    listeners.current.add(fn);
    return () => listeners.current.delete(fn);
  }, []);
  const check = useCallback(() => listeners.current.forEach((fn) => fn()), []);
  return { check, value: { register } };
}

export const RevealProvider = RevealContext.Provider;

function useEntrance(delay: number, start: boolean, reduced: boolean) {
  const progress = useRef(new Animated.Value(reduced ? 1 : 0)).current;
  useEffect(() => {
    if (!start || reduced) return;
    Animated.timing(progress, {
      toValue: 1,
      duration: 750,
      delay,
      easing: EASE_OUT,
      useNativeDriver: NATIVE,
    }).start();
  }, [start, reduced, delay, progress]);
  return {
    opacity: progress,
    transform: [{ translateY: progress.interpolate({ inputRange: [0, 1], outputRange: [24, 0] }) }],
  };
}

interface MotionProps {
  delay?: number;
  style?: StyleProp<ViewStyle>;
  children: React.ReactNode;
}

/** Fades and rises in once, on mount. */
export function FadeIn({ delay = 0, style, children }: MotionProps) {
  const reduced = useReducedMotion();
  const anim = useEntrance(delay, true, reduced);
  return <Animated.View style={[style, anim]}>{children}</Animated.View>;
}

/** Fades and rises in the first time it scrolls into view. */
export function Reveal({ delay = 0, style, children }: MotionProps) {
  const reduced = useReducedMotion();
  const ctx = useContext(RevealContext);
  const ref = useRef<View>(null);
  const { height } = useWindowDimensions();
  const [shown, setShown] = useState(false);

  useEffect(() => {
    if (shown || !ctx) return;
    const check = () =>
      ref.current?.measureInWindow((_x, y) => {
        if (y < height * 0.92) setShown(true);
      });
    const unregister = ctx.register(check);
    // Content already on screen at load reveals without a scroll.
    const t = setTimeout(check, 50);
    return () => {
      unregister();
      clearTimeout(t);
    };
  }, [ctx, shown, height]);

  const anim = useEntrance(delay, shown || !ctx, reduced);
  return (
    <Animated.View ref={ref} style={[style, anim]}>
      {children}
    </Animated.View>
  );
}

// ── Looping accents ────────────────────────────────────────────────────────

function useLoop(duration: number, reduced: boolean) {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (reduced) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(v, { toValue: 1, duration, easing: Easing.inOut(Easing.sin), useNativeDriver: NATIVE }),
        Animated.timing(v, { toValue: 0, duration, easing: Easing.inOut(Easing.sin), useNativeDriver: NATIVE }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [v, duration, reduced]);
  return v;
}

/** Drifts up and down by `distance` px. */
export function Float({ distance = 10, duration = 3000, style, children }: MotionProps & { distance?: number; duration?: number }) {
  const reduced = useReducedMotion();
  const v = useLoop(duration, reduced);
  const translateY = v.interpolate({ inputRange: [0, 1], outputRange: [0, -distance] });
  return <Animated.View style={[style, { transform: [{ translateY }] }]}>{children}</Animated.View>;
}

/** Breathes opacity between `from` and 1. */
export function Pulse({ from = 0.55, duration = 1500, style, children }: MotionProps & { from?: number; duration?: number }) {
  const reduced = useReducedMotion();
  const v = useLoop(duration, reduced);
  const opacity = reduced ? 1 : v.interpolate({ inputRange: [0, 1], outputRange: [from, 1] });
  return <Animated.View style={[style, { opacity }]}>{children}</Animated.View>;
}

/** Small bouncing arrow, used on "Learn more". */
export function BobArrow({ style }: { style?: StyleProp<TextStyle> }) {
  const reduced = useReducedMotion();
  const v = useLoop(700, reduced);
  const translateY = v.interpolate({ inputRange: [0, 1], outputRange: [0, 4] });
  return <Animated.Text style={[style, { transform: [{ translateY }] }]}>↓</Animated.Text>;
}

/** Cycles single-line phrases upward, one every few seconds. */
export function CycleText({
  items,
  lineHeight = 24,
  interval = 2500,
  style,
}: {
  items: string[];
  lineHeight?: number;
  interval?: number;
  style?: StyleProp<TextStyle>;
}) {
  const reduced = useReducedMotion();
  const y = useRef(new Animated.Value(0)).current;
  const index = useRef(0);

  useEffect(() => {
    if (reduced) return;
    const id = setInterval(() => {
      index.current += 1;
      Animated.timing(y, {
        toValue: -index.current * lineHeight,
        duration: 500,
        easing: Easing.bezier(0.7, 0, 0.3, 1),
        useNativeDriver: NATIVE,
      }).start(() => {
        // The list ends with a copy of the first item; snap back seamlessly.
        if (index.current === items.length) {
          index.current = 0;
          y.setValue(0);
        }
      });
    }, interval);
    return () => clearInterval(id);
  }, [items.length, lineHeight, interval, reduced, y]);

  return (
    <View style={{ height: lineHeight, overflow: 'hidden', flex: 1, minWidth: 0 }}>
      <Animated.View style={{ transform: [{ translateY: y }] }}>
        {[...items, items[0]].map((item, i) => (
          <Text key={i} numberOfLines={1} style={[style, { height: lineHeight, lineHeight }]}>
            {item}
          </Text>
        ))}
      </Animated.View>
    </View>
  );
}
