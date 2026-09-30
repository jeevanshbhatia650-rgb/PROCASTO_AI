import { BookOpenCheck, Quote, Zap, type LucideIcon } from "lucide-react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Backdrop, body, C, clamp, display, EASE, Rise, Tag } from "../ui";

const CODES = ["4C", "5E", "UE", "9C1", "tE1", "dE", "HC", "LE", "8CA1", "3E", "OE", "bE2", "nF", "DC", "PE", "AE5", "4E2", "UB1"];

/** What the answers are built on: real, openly licensed Samsung fault data. */
export const Data: React.FC = () => {
  const frame = useCurrentFrame();
  const count = Math.round(interpolate(frame, [8, 70], [0, 157], { ...clamp, easing: EASE }));
  return (
    <AbsoluteFill>
      <Backdrop dark />
      <AbsoluteFill style={{ alignItems: "center", paddingTop: 120, color: "#fff", textAlign: "center" }}>
        <div style={{ fontFamily: display, fontWeight: 300, fontSize: 240, lineHeight: 1, letterSpacing: -6 }}>{count}</div>
        <Rise at={20}>
          <div style={{ fontFamily: display, fontSize: 56, marginTop: 10 }}>real Samsung washer fault codes</div>
        </Rise>
        <Rise at={40}>
          <div style={{ fontFamily: body, fontSize: 30, color: "rgba(255,255,255,0.6)", marginTop: 14 }}>
            Every spelling of a fault, its meaning and what to do, built into the answers.
          </div>
        </Rise>
        <div style={{ position: "relative", width: "100%", height: 110, overflow: "hidden", marginTop: 56, opacity: interpolate(frame, [50, 70], [0, 1], clamp) }}>
          <div style={{ position: "absolute", display: "flex", gap: 22, left: interpolate(frame, [50, 300], [0, -900]), top: 20 }}>
            {[...CODES, ...CODES].map((code, i) => (
              <span key={i} style={{ fontFamily: display, fontWeight: 500, fontSize: 44, color: C.amber, padding: "10px 28px", borderRadius: 18, border: "1px solid rgba(255,159,10,0.35)" }}>
                {code}
              </span>
            ))}
          </div>
        </div>
        <Rise at={110} style={{ display: "flex", gap: 16, marginTop: 50 }}>
          <Tag dark>Open data · MIT licence</Tag>
          <Tag dark>Pinned commit · hash-checked</Tag>
          <Tag dark>Search by keyword and by meaning</Tag>
        </Rise>
        <Rise at={150}>
          <div style={{ fontFamily: body, fontSize: 24, color: "rgba(255,255,255,0.45)", marginTop: 40, maxWidth: 1400, lineHeight: 1.5 }}>
            Source: ha-samsung-washer-local (MIT), rewritten in its own words. Search: BM25 keywords plus bge-small embeddings,
            fused and held in memory, so no vector database is needed at this size.
          </div>
        </Rise>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const PILLARS: { Icon: LucideIcon; title: string; text: string }[] = [
  { Icon: BookOpenCheck, title: "Explains, not just shows", text: "The why and the fix, from that model's own manual." },
  { Icon: Zap, title: "Ahead of you", text: "Starts looking while you are still talking." },
  { Icon: Quote, title: "Shows its work", text: "Every answer cites live state or the manual page." },
];

export const Different: React.FC = () => (
  <AbsoluteFill>
    <Backdrop />
    <AbsoluteFill style={{ alignItems: "center", paddingTop: 170, color: C.ink }}>
      <Rise at={0}>
        <div style={{ fontFamily: display, fontSize: 84, letterSpacing: -1.5 }}>Why it's different.</div>
      </Rise>
      <div style={{ display: "flex", gap: 40, marginTop: 110 }}>
        {PILLARS.map(({ Icon, title, text }, i) => (
          <Rise key={title} at={20 + i * 14}>
            <div style={{ width: 460, padding: 44, borderRadius: 36, background: "rgba(255,255,255,0.9)", boxShadow: "0 30px 80px rgba(0,0,0,0.08)" }}>
              <span style={{ width: 76, height: 76, borderRadius: 99, background: C.ink, display: "grid", placeItems: "center" }}>
                <Icon size={36} color="#fff" />
              </span>
              <div style={{ fontFamily: display, fontSize: 40, fontWeight: 500, marginTop: 34 }}>{title}</div>
              <div style={{ fontFamily: body, fontSize: 28, color: C.mute, marginTop: 14, lineHeight: 1.4 }}>{text}</div>
            </div>
          </Rise>
        ))}
      </div>
    </AbsoluteFill>
  </AbsoluteFill>
);

export const End: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Backdrop />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center", color: C.ink }}>
        <div
          style={{
            fontFamily: display,
            fontWeight: 300,
            fontSize: 150,
            letterSpacing: interpolate(frame, [0, 50], [40, 16], { ...clamp, easing: EASE }),
            opacity: interpolate(frame, [0, 20], [0, 1], clamp),
          }}
        >
          PROCASTO
        </div>
        <Rise at={20}>
          <div style={{ fontFamily: body, fontSize: 40, color: C.mute, marginTop: 16 }}>Your home, explained.</div>
        </Rise>
        <Rise at={40}>
          <div style={{ marginTop: 56, fontFamily: body, fontSize: 32, fontWeight: 600, color: "#fff", background: C.ink, padding: "22px 48px", borderRadius: 99 }}>
            Try the live demo
          </div>
        </Rise>
      </AbsoluteFill>
      <Rise at={60} style={{ position: "absolute", bottom: 50, width: "100%", textAlign: "center" }}>
        <div style={{ fontFamily: body, fontSize: 20, color: "rgba(17,17,19,0.45)", lineHeight: 1.5 }}>
          An independent project, not affiliated with Samsung. SmartThings is a trademark of Samsung Electronics.
          <br />
          The connection sequence is an illustration with sample devices. Dryer and AC manuals in the demo are sample data.
        </div>
      </Rise>
    </AbsoluteFill>
  );
};
