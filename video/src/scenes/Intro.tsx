import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Backdrop, body, C, clamp, display, EASE, Rise } from "../ui";

/** A washer display blinking a code nobody understands. */
export const Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const blink = frame < 44 ? (Math.floor(frame / 9) % 2 === 0 ? 1 : 0.2) : 1;
  return (
    <AbsoluteFill>
      <Backdrop dark />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 80 }}>
        <div
          style={{
            scale: String(interpolate(frame, [0, 150], [1, 1.07], clamp)),
            width: 540,
            height: 250,
            borderRadius: 46,
            background: "linear-gradient(180deg, #1c1c1f, #0e0e10)",
            border: "1px solid rgba(255,255,255,0.08)",
            boxShadow: "inset 0 2px 30px rgba(0,0,0,0.7), 0 40px 120px rgba(0,0,0,0.6)",
            display: "grid",
            placeItems: "center",
          }}
        >
          <span style={{ fontFamily: display, fontWeight: 500, fontSize: 156, letterSpacing: 12, color: C.amber, opacity: blink, textShadow: `0 0 36px ${C.amber}88` }}>
            4C
          </span>
        </div>
        <div style={{ textAlign: "center", color: "#fff" }}>
          <Rise at={48}>
            <div style={{ fontFamily: display, fontSize: 80, letterSpacing: -1.5 }}>Your washer says 4C.</div>
          </Rise>
          <Rise at={92}>
            <div style={{ fontFamily: display, fontSize: 80, letterSpacing: -1.5, color: "rgba(255,255,255,0.45)" }}>Now what?</div>
          </Rise>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const Problem: React.FC = () => (
  <AbsoluteFill>
    <Backdrop />
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center", color: C.ink }}>
      <Rise at={4}>
        <div style={{ fontFamily: display, fontSize: 96, letterSpacing: -2 }}>Smart homes show you what.</div>
      </Rise>
      <Rise at={42}>
        <div style={{ fontFamily: display, fontSize: 96, letterSpacing: -2, marginTop: 10 }}>
          Never <span style={{ color: C.blue }}>why</span>.
        </div>
      </Rise>
    </AbsoluteFill>
  </AbsoluteFill>
);

export const Reveal: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Backdrop />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center", color: C.ink }}>
        <div
          style={{
            fontFamily: display,
            fontWeight: 300,
            fontSize: 170,
            letterSpacing: interpolate(frame, [0, 60], [70, 16], { ...clamp, easing: EASE }),
            opacity: interpolate(frame, [0, 24], [0, 1], clamp),
          }}
        >
          PROCASTO
        </div>
        <Rise at={36}>
          <div style={{ fontFamily: body, fontSize: 40, color: C.mute, marginTop: 20 }}>Your home, explained.</div>
        </Rise>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
