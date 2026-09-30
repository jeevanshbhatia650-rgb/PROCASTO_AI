import {
  AirVent,
  Bot,
  Check,
  CookingPot,
  DoorClosed,
  Fan,
  Lightbulb,
  LoaderCircle,
  Plug,
  PlugZap,
  Refrigerator,
  Shirt,
  Tv,
  Utensils,
  WashingMachine,
  type LucideIcon,
} from "lucide-react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Backdrop, body, C, clamp, display, EASE, Rise, Statement, Tag } from "../ui";

type Device = { name: string; room: string; Icon: LucideIcon };

const DEVICES: Device[] = [
  { name: "Washer", room: "Laundry room", Icon: WashingMachine },
  { name: "Dryer", room: "Laundry room", Icon: Shirt },
  { name: "Air conditioner", room: "Living room", Icon: AirVent },
  { name: "Refrigerator", room: "Kitchen", Icon: Refrigerator },
  { name: "TV", room: "Living room", Icon: Tv },
  { name: "Robot vacuum", room: "Hallway", Icon: Bot },
  { name: "Ceiling light", room: "Bedroom", Icon: Lightbulb },
  { name: "Dishwasher", room: "Kitchen", Icon: Utensils },
  { name: "Smart plug", room: "Office", Icon: Plug },
  { name: "Front door", room: "Entrance", Icon: DoorClosed },
  { name: "Oven", room: "Kitchen", Icon: CookingPot },
  { name: "Air purifier", room: "Bedroom", Icon: Fan },
];

const CARD = { left: 1010, top: 130, width: 760, height: 820 };

const Cursor: React.FC = () => {
  const frame = useCurrentFrame();
  const x = interpolate(frame, [40, 75, 112, 150], [640, 330, 330, 650], { ...clamp, easing: EASE });
  const y = interpolate(frame, [40, 75, 112, 150], [760, 575, 575, 660], { ...clamp, easing: EASE });
  const press = frame >= 78 && frame < 86 ? 0.8 : frame >= 158 && frame < 166 ? 0.8 : 1;
  return (
    <div
      style={{
        position: "absolute",
        left: x - 16,
        top: y - 16,
        width: 32,
        height: 32,
        borderRadius: 99,
        background: "rgba(17,17,19,0.85)",
        border: "3px solid #fff",
        boxShadow: "0 6px 20px rgba(0,0,0,0.3)",
        scale: String(press),
        opacity: interpolate(frame, [30, 40, 180, 192], [0, 1, 1, 0], clamp),
      }}
    />
  );
};

const stage = (frame: number, start: number, end: number) => ({
  position: "absolute" as const,
  inset: 0,
  padding: 48,
  opacity: interpolate(frame, [start, start + 14, end - 10, end], [0, 1, 1, 0], clamp),
  translate: interpolate(frame, [start, start + 22], ["40px 0px", "0px 0px"], { ...clamp, easing: EASE }),
});

const Pill: React.FC<{ children: React.ReactNode; tone?: "ok" | "muted" }> = ({ children, tone = "muted" }) => (
  <span
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 8,
      fontFamily: body,
      fontSize: 22,
      padding: "8px 18px",
      borderRadius: 99,
      background: tone === "ok" ? "rgba(31,157,85,0.12)" : "rgba(17,17,19,0.06)",
      color: tone === "ok" ? C.ok : C.mute,
    }}
  >
    {children}
  </span>
);

/** The first run: one button, one approval, and every device the account shares, counted. */
export const Connect: React.FC = () => {
  const frame = useCurrentFrame();
  const found = Math.round(interpolate(frame, [215, 330], [0, DEVICES.length], clamp));
  const pressA = frame >= 78 && frame < 88 ? 0.96 : 1;
  const pressB = frame >= 158 && frame < 168 ? 0.96 : 1;

  return (
    <AbsoluteFill>
      <Backdrop />
      <div style={{ position: "absolute", left: 150, top: 350, width: 760 }}>
        <Statement
          align="left"
          title="Connect once."
          sub="Sign in with your Samsung account. Every device you share shows up, counted."
        />
        <Rise at={30} style={{ display: "flex", gap: 14, marginTop: 44, flexWrap: "wrap" }}>
          <Tag>No API keys</Tag>
          <Tag>No setup</Tag>
          <Tag>Login encrypted at rest</Tag>
        </Rise>
      </div>

      <Rise at={6} style={{ position: "absolute", ...CARD }}>
        <div
          style={{
            position: "relative",
            width: CARD.width,
            height: CARD.height,
            borderRadius: 40,
            background: "rgba(255,255,255,0.92)",
            boxShadow: "0 50px 120px rgba(0,0,0,0.14), 0 8px 24px rgba(0,0,0,0.06)",
            overflow: "hidden",
            fontFamily: body,
            color: C.ink,
          }}
        >
          {/* 1. The Devices page before connecting */}
          <div style={stage(frame, 0, 100)}>
            <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
              <span style={{ width: 72, height: 72, borderRadius: 99, background: C.ink, display: "grid", placeItems: "center" }}>
                <PlugZap size={34} color="#fff" />
              </span>
              <div>
                <div style={{ fontFamily: display, fontSize: 40, fontWeight: 500 }}>Samsung SmartThings</div>
                <div style={{ marginTop: 8 }}>
                  <Pill>Not connected</Pill>
                </div>
              </div>
            </div>
            <p style={{ fontSize: 28, color: C.mute, lineHeight: 1.45, marginTop: 44 }}>
              Connect once through Samsung. Every device you approve appears here, and supported readings update live.
            </p>
            <div
              style={{
                position: "absolute",
                left: 48,
                top: 520,
                width: 360,
                height: 76,
                borderRadius: 99,
                background: C.ink,
                color: "#fff",
                display: "grid",
                placeItems: "center",
                fontSize: 28,
                fontWeight: 600,
                scale: String(pressA),
              }}
            >
              Connect SmartThings
            </div>
          </div>

          {/* 2. The approval screen (an illustration: no real login is shown) */}
          <div style={stage(frame, 100, 205)}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 26, fontWeight: 600, color: C.mute }}>SmartThings</span>
              <Pill>Example</Pill>
            </div>
            <div style={{ fontFamily: display, fontSize: 44, fontWeight: 500, marginTop: 40, lineHeight: 1.15 }}>
              PROCASTO would like to
            </div>
            {["See your devices and rooms", "Read their live status", "Change a device, only after you confirm"].map((line, i) => (
              <div
                key={line}
                style={{
                  display: "flex",
                  gap: 16,
                  alignItems: "center",
                  fontSize: 28,
                  marginTop: i === 0 ? 40 : 22,
                  opacity: interpolate(frame, [118 + i * 8, 130 + i * 8], [0, 1], clamp),
                }}
              >
                <span style={{ width: 40, height: 40, borderRadius: 99, background: "rgba(31,157,85,0.12)", display: "grid", placeItems: "center" }}>
                  <Check size={22} color={C.ok} />
                </span>
                {line}
              </div>
            ))}
            <div style={{ position: "absolute", left: 48, top: 612, width: 300, height: 72, borderRadius: 99, border: `2px solid ${C.hair}`, display: "grid", placeItems: "center", fontSize: 26, color: C.mute }}>
              Deny
            </div>
            <div
              style={{
                position: "absolute",
                left: 400,
                top: 612,
                width: 312,
                height: 72,
                borderRadius: 99,
                background: C.ink,
                color: "#fff",
                display: "grid",
                placeItems: "center",
                fontSize: 26,
                fontWeight: 600,
                scale: String(pressB),
              }}
            >
              Allow
            </div>
          </div>

          {/* 3. Everything the account shares, counted */}
          <div style={stage(frame, 205, 99999)}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontFamily: display, fontSize: 40, fontWeight: 500 }}>
                  {found === DEVICES.length ? `${found} devices found` : "Finding your devices"}
                </div>
                <div style={{ fontSize: 24, color: C.mute, marginTop: 6 }}>Shared from Samsung, with their rooms</div>
              </div>
              {found === DEVICES.length ? (
                <Pill tone="ok">
                  <span style={{ width: 10, height: 10, borderRadius: 99, background: C.okBright }} /> Live
                </Pill>
              ) : (
                <LoaderCircle size={36} color={C.mute} style={{ rotate: `${frame * 9}deg` }} />
              )}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 34 }}>
              {DEVICES.map(({ name, room, Icon }, i) => {
                const at = 222 + i * 9;
                return (
                  <div
                    key={name}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 14,
                      padding: 14,
                      borderRadius: 20,
                      background: "rgba(17,17,19,0.035)",
                      opacity: interpolate(frame, [at, at + 10], [0, 1], clamp),
                      translate: interpolate(frame, [at, at + 16], ["0px 18px", "0px 0px"], { ...clamp, easing: EASE }),
                    }}
                  >
                    <span style={{ width: 52, height: 52, borderRadius: 14, background: "#fff", display: "grid", placeItems: "center" }}>
                      <Icon size={26} color={C.ink} />
                    </span>
                    <span>
                      <div style={{ fontSize: 23, fontWeight: 600 }}>{name}</div>
                      <div style={{ fontSize: 19, color: C.mute }}>{room}</div>
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
          <Cursor />
        </div>
      </Rise>
      <Rise at={215} style={{ position: "absolute", right: 150, bottom: 70 }}>
        <Tag>Illustration with sample devices</Tag>
      </Rise>
    </AbsoluteFill>
  );
};

const FOLLOWED = new Set(["Washer", "Dryer", "Air conditioner", "Refrigerator"]);

/** Choosing which devices may interrupt you. */
export const Follow: React.FC = () => {
  const frame = useCurrentFrame();
  const rows = DEVICES.slice(0, 8);
  const onAt = (name: string) => 50 + [...FOLLOWED].indexOf(name) * 18;
  const count = [...FOLLOWED].filter((n) => frame >= onAt(n) + 6).length;
  return (
    <AbsoluteFill>
      <Backdrop />
      <div style={{ position: "absolute", top: 110, width: "100%" }}>
        <Statement title="Follow what matters." sub="Pick the devices that may alert you. You can still ask about all of them." />
      </div>
      <Rise at={14} style={{ position: "absolute", left: 360, top: 400, width: 1200 }}>
        <div style={{ borderRadius: 40, background: "rgba(255,255,255,0.92)", boxShadow: "0 50px 120px rgba(0,0,0,0.12)", padding: 40, fontFamily: body, color: C.ink }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 26 }}>
            <div style={{ fontFamily: display, fontSize: 36, fontWeight: 500 }}>Your connected devices</div>
            <div style={{ fontSize: 24, color: C.mute }}>{count} followed</div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            {rows.map(({ name, room, Icon }) => {
              const on = FOLLOWED.has(name) && frame >= onAt(name);
              const knob = FOLLOWED.has(name) ? interpolate(frame, [onAt(name), onAt(name) + 8], [0, 28], { ...clamp, easing: EASE }) : 0;
              return (
                <div key={name} style={{ display: "flex", alignItems: "center", gap: 16, padding: 16, borderRadius: 22, background: "rgba(17,17,19,0.035)" }}>
                  <span style={{ width: 54, height: 54, borderRadius: 14, background: "#fff", display: "grid", placeItems: "center" }}>
                    <Icon size={27} />
                  </span>
                  <span style={{ flex: 1 }}>
                    <div style={{ fontSize: 24, fontWeight: 600 }}>{name}</div>
                    <div style={{ fontSize: 19, color: C.mute }}>{room}</div>
                  </span>
                  <span style={{ width: 66, height: 38, borderRadius: 99, padding: 4, background: on ? C.okBright : "rgba(17,17,19,0.15)" }}>
                    <span style={{ display: "block", width: 30, height: 30, borderRadius: 99, background: "#fff", translate: `${knob}px 0px`, boxShadow: "0 2px 6px rgba(0,0,0,0.2)" }} />
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </Rise>
    </AbsoluteFill>
  );
};
