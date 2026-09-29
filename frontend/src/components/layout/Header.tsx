import { useStore } from "../../lib/store";
import { KeyboardIcon, LogoMark, SpeakerIcon } from "../icons";
import { ConnectSmartThings } from "../controls/ConnectSmartThings";
import { ReplayButton } from "../controls/ReplayButton";
import { HoodToggle } from "./HoodToggle";

const SPIKE_W = 2500;

function ConnectionStatus() {
  const connection = useStore((s) => s.connection);
  const provider = useStore((s) => s.hello?.provider);
  const live = connection === "open";
  return (
    <span className="flex items-center gap-1.5" role="status">
      <span className={`h-1.5 w-1.5 rounded-full ${live ? "bg-ok-dark" : "bg-run-dark"}`} />
      {live ? (provider === "smartthings" ? "SmartThings" : "Simulated home") : "Reconnecting…"}
    </span>
  );
}

const SHORTCUTS = "Hold Space to talk · H under the hood · R replay demo · 1–5 break something";

export function Header() {
  const voiceOn = useStore((s) => s.voiceOn);
  const toggleVoice = useStore((s) => s.toggleVoice);
  const llm = useStore((s) => s.hello?.llm);
  const devices = useStore((s) => s.devices);
  const list = Object.values(devices);
  const attention = list.filter((d) => d.attributes.error_code || Number(d.attributes.power_w) > SPIKE_W).length;

  return (
    <header className="sticky top-0 z-40">
      <div className="bg-black text-white">
        <div className="mx-auto flex h-11 max-w-[1440px] items-center gap-4 px-4 t-fine md:px-6">
          <LogoMark size={20} />
          <span className="text-[13px] font-semibold tracking-tight">PROCASTO-AI</span>
          <span className="hidden text-white/55 lg:inline">It starts looking things up while you’re still talking.</span>
          <div className="ml-auto flex items-center gap-4 text-white/80">
            <ConnectSmartThings />
            <ConnectionStatus />
            <span className="hidden md:inline" title="Who writes the explanation sentence on each card">
              Phrasing: {llm === "gemini" ? "Gemini" : "templates"}
            </span>
            <button
              type="button"
              onClick={toggleVoice}
              aria-pressed={voiceOn}
              aria-label={voiceOn ? "Mute voice replies" : "Turn voice replies on"}
              className="pressable rounded-full p-1 text-white/80"
            >
              <SpeakerIcon muted={!voiceOn} size={17} />
            </button>
            <span className="hidden text-white/80 xl:inline-flex" title={SHORTCUTS} aria-label={SHORTCUTS}>
              <KeyboardIcon size={17} />
            </span>
          </div>
        </div>
      </div>
      <div className="frosted border-b border-black/[0.06]">
        <div className="mx-auto flex h-[52px] max-w-[1440px] items-center gap-3 px-4 md:px-6">
          <h1 className="t-tagline">Home</h1>
          <span className="hidden t-caption text-ink-48 sm:inline">
            {list.length} devices · {attention ? `${attention} need${attention === 1 ? "s" : ""} attention` : "all normal"}
          </span>
          <div className="ml-auto flex items-center gap-3 sm:gap-5">
            <HoodToggle />
            <ReplayButton />
          </div>
        </div>
      </div>
    </header>
  );
}
