import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadMontserrat } from "@remotion/google-fonts/Montserrat";
import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from "remotion";

export const display = loadMontserrat("normal", { weights: ["300", "400", "500", "600"], subsets: ["latin"] }).fontFamily;
export const body = loadInter("normal", { weights: ["400", "500", "600"], subsets: ["latin"] }).fontFamily;

export const C = {
  ink: "#111113",
  canvas: "#F4F2EE",
  mute: "#6E6E73",
  hair: "rgba(17,17,19,0.08)",
  ok: "#1F9D55",
  okBright: "#34C759",
  bad: "#E0443B",
  amber: "#FF9F0A",
  blue: "#0071E3",
  night: "#0A0A0B",
};

export const EASE = Easing.bezier(0.16, 1, 0.3, 1);
export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** Fades and lifts its children in at frame `at`; optionally fades them out at `out`. */
export const Rise: React.FC<{ at: number; out?: number; style?: CSSProperties; children: ReactNode }> = ({
  at,
  out,
  style,
  children,
}) => {
  const frame = useCurrentFrame();
  const fadeOut = out === undefined ? 1 : interpolate(frame, [out, out + 12], [1, 0], clamp);
  return (
    <div
      style={{
        opacity: interpolate(frame, [at, at + 18], [0, 1], { ...clamp, easing: EASE }) * fadeOut,
        translate: interpolate(frame, [at, at + 26], ["0px 36px", "0px 0px"], { ...clamp, easing: EASE }),
        ...style,
      }}
    >
      {children}
    </div>
  );
};

/** The Samsung-ad layout: one quiet statement at the top, the product under it. */
export const Statement: React.FC<{ at?: number; title: ReactNode; sub?: ReactNode; dark?: boolean; align?: "center" | "left" }> = ({
  at = 0,
  title,
  sub,
  dark = false,
  align = "center",
}) => (
  <div style={{ textAlign: align, color: dark ? "#fff" : C.ink }}>
    <Rise at={at}>
      <div style={{ fontFamily: display, fontWeight: 400, fontSize: 76, letterSpacing: -1.5, lineHeight: 1.05 }}>{title}</div>
    </Rise>
    {sub && (
      <Rise at={at + 10}>
        <div style={{ fontFamily: body, fontSize: 32, marginTop: 18, color: dark ? "rgba(255,255,255,0.62)" : C.mute }}>
          {sub}
        </div>
      </Rise>
    )}
  </div>
);

export const Backdrop: React.FC<{ dark?: boolean }> = ({ dark }) => (
  <AbsoluteFill
    style={{
      background: dark
        ? `radial-gradient(1200px 700px at 50% 30%, #1c1c1f 0%, ${C.night} 70%)`
        : `radial-gradient(1400px 800px at 50% 20%, #ffffff 0%, ${C.canvas} 75%)`,
    }}
  />
);

/**
 * A browser window showing a real capture at the app's own 1440 x 900 viewport, so overlay coordinates are the
 * app's CSS pixels. `scroll` moves the page, like a visitor scrolling.
 */
export const Browser: React.FC<{ src: string; scroll?: number; children?: ReactNode; style?: CSSProperties }> = ({
  src,
  scroll = 0,
  children,
  style,
}) => (
  <div
    style={{
      width: 1440,
      borderRadius: 24,
      overflow: "hidden",
      background: "#fff",
      boxShadow: "0 50px 120px rgba(0,0,0,0.16), 0 10px 30px rgba(0,0,0,0.08)",
      ...style,
    }}
  >
    <div style={{ height: 46, display: "flex", alignItems: "center", gap: 9, padding: "0 20px", background: "#F7F7F8", borderBottom: `1px solid ${C.hair}` }}>
      {[0, 1, 2].map((i) => (
        <span key={i} style={{ width: 13, height: 13, borderRadius: 99, background: "#DADADF" }} />
      ))}
      <span style={{ margin: "0 auto", fontFamily: body, fontSize: 17, color: C.mute, background: "#fff", padding: "5px 60px", borderRadius: 99 }}>
        procasto · live demo
      </span>
    </div>
    <div style={{ position: "relative", width: 1440, height: 900, overflow: "hidden" }}>
      <Img src={staticFile(src)} style={{ position: "absolute", left: 0, top: -scroll, width: 1440 }} />
      <div style={{ position: "absolute", left: 0, top: -scroll, width: 1440 }}>{children}</div>
    </div>
  </div>
);

/** A soft pulsing ring that points at part of a capture. */
export const Ring: React.FC<{ at: number; until?: number; x: number; y: number; w: number; h: number; color?: string; radius?: number }> = ({
  at,
  until = 99999,
  x,
  y,
  w,
  h,
  color = C.blue,
  radius = 99,
}) => {
  const frame = useCurrentFrame();
  const t = Math.max(0, frame - at);
  return (
    <div
      style={{
        position: "absolute",
        left: x - 8,
        top: y - 8,
        width: w + 16,
        height: h + 16,
        borderRadius: radius,
        border: `4px solid ${color}`,
        opacity: interpolate(frame, [at, at + 10, until, until + 10], [0, 1, 1, 0], clamp),
        scale: String(1 + 0.04 * Math.sin(t / 7)),
        boxShadow: `0 0 0 ${8 + 6 * Math.sin(t / 7)}px ${color}22`,
      }}
    />
  );
};

export const Tag: React.FC<{ children: ReactNode; dark?: boolean; style?: CSSProperties }> = ({ children, dark, style }) => (
  <span
    style={{
      fontFamily: body,
      fontSize: 22,
      padding: "10px 20px",
      borderRadius: 99,
      background: dark ? "rgba(255,255,255,0.1)" : "rgba(17,17,19,0.06)",
      color: dark ? "rgba(255,255,255,0.8)" : C.mute,
      whiteSpace: "nowrap",
      ...style,
    }}
  >
    {children}
  </span>
);
