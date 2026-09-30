import type { ReactNode } from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Backdrop, Browser, C, clamp, EASE, Ring, Rise, Statement, Tag } from "../ui";

const SHOT_SCALE = 0.88;
const SHOT_LEFT = (1920 - 1440 * SHOT_SCALE) / 2;
const SHOT_TOP = 262;
const BAR = 46; // the browser's title bar, above the page

/**
 * A real capture under a statement. `zoom` pushes the camera in on `focus` (page pixels) and glides that point
 * toward the middle of the frame, the way a product film moves in on a detail.
 */
const Shot: React.FC<{
  src: string;
  scroll?: number;
  zoom?: number;
  focus?: [number, number];
  children?: ReactNode;
}> = ({ src, scroll = 0, zoom = 1, focus = [720, 450], children }) => {
  const fx = SHOT_LEFT + focus[0] * SHOT_SCALE;
  const fy = SHOT_TOP + (focus[1] + BAR - scroll) * SHOT_SCALE;
  const shift = Math.min(1, Math.max(0, (zoom - 1) / 0.6)); // how far the detail has travelled to the middle
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        transformOrigin: `${fx}px ${fy}px`,
        scale: String(zoom),
        translate: `${(960 - fx) * shift}px ${(560 - fy) * shift}px`,
      }}
    >
      <div style={{ position: "absolute", left: SHOT_LEFT, top: SHOT_TOP, transformOrigin: "0 0", scale: String(SHOT_SCALE) }}>
        <Browser src={src} scroll={scroll}>
          {children}
        </Browser>
      </div>
    </div>
  );
};

const Top: React.FC<{ children: ReactNode; out?: number }> = ({ children, out }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ position: "absolute", top: 56, width: "100%", opacity: out === undefined ? 1 : interpolate(frame, [out, out + 14], [1, 0], clamp) }}>
      {children}
    </div>
  );
};

const rise = (frame: number) => ({
  opacity: interpolate(frame, [0, 20], [0, 1], clamp),
  translate: interpolate(frame, [0, 30], ["0px 80px", "0px 0px"], { ...clamp, easing: EASE }),
});

export const Home: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Backdrop />
      <Top>
        <Statement title="One room at a time." sub="Live power underneath, sampled every 3 seconds." />
      </Top>
      <div style={{ position: "absolute", inset: 0, ...rise(frame) }}>
        <Shot src="shot-home-full.png" scroll={interpolate(frame, [110, 210], [0, 283], { ...clamp, easing: EASE })}>
          <Ring at={50} until={105} x={1300} y={505} w={78} h={38} color={C.ok} />
        </Shot>
      </div>
    </AbsoluteFill>
  );
};

export const Alert: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Backdrop />
      <Top out={52}>
        <Statement title="Something breaks? You hear first." sub="Only for devices you follow. Tap Ask for the why." />
      </Top>
      <div style={{ position: "absolute", inset: 0, ...rise(frame) }}>
        <Shot src="shot-alert.png" zoom={interpolate(frame, [60, 150], [1, 2.1], { ...clamp, easing: EASE })} focus={[720, 45]}>
          <Ring at={125} x={844} y={32} w={36} h={26} radius={10} />
        </Shot>
      </div>
    </AbsoluteFill>
  );
};

export const Answer: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Backdrop />
      <Top>
        <Statement title="It explains the fault." sub="Live state plus the manual. Every answer shows its source." />
      </Top>
      <div style={{ position: "absolute", inset: 0, ...rise(frame) }}>
        <Shot src="shot-answer-full.png" scroll={interpolate(frame, [40, 160], [0, 598], { ...clamp, easing: EASE })}>
          <Ring at={175} x={946} y={980} w={250} h={26} radius={12} />
          <Ring at={235} x={305} y={1236} w={570} h={92} radius={20} color={C.ok} />
        </Shot>
      </div>
    </AbsoluteFill>
  );
};

export const Speed: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Backdrop />
      <Top out={62}>
        <Statement title="It starts before you finish." sub="Lookups begin mid-sentence. Interrupt it, correct it, come back." />
      </Top>
      <div style={{ position: "absolute", inset: 0, ...rise(frame) }}>
        <Shot src="shot-hood.png" zoom={interpolate(frame, [70, 170], [1, 1.75], { ...clamp, easing: EASE })} focus={[1130, 520]}>
          <Ring at={165} x={892} y={270} w={178} h={72} radius={20} />
        </Shot>
      </div>
      <Rise at={175} style={{ position: "absolute", top: 48, right: 60 }}>
        <Tag style={{ background: "#fff", boxShadow: "0 8px 24px rgba(0,0,0,0.12)" }}>Under the hood · measured on the scripted demo</Tag>
      </Rise>
    </AbsoluteFill>
  );
};

export const Voice: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Backdrop />
      <div style={{ position: "absolute", left: 200, top: 380, width: 820 }}>
        <Statement align="left" title="Just ask." sub="Voice first. Talk over it or change your mind. The transcript stays out of your way." />
      </div>
      <div
        style={{
          position: "absolute",
          right: 300,
          top: 110,
          width: 404,
          height: 862,
          borderRadius: 64,
          background: "#111",
          padding: 14,
          boxShadow: "0 60px 120px rgba(0,0,0,0.25)",
          ...rise(frame),
        }}
      >
        <div style={{ width: 376, height: 834, borderRadius: 52, overflow: "hidden", position: "relative" }}>
          <Img src={staticFile("shot-phone-assistant.png")} style={{ width: 376, position: "absolute", top: 0 }} />
        </div>
      </div>
    </AbsoluteFill>
  );
};
