import { useCallback, useEffect } from "react";
import { useSearchParams } from "react-router";
import { ErrorBoundary } from "../../components/ErrorBoundary";
import { DemoCaption } from "../../components/controls/DemoCaption";
import { ReplayButton } from "../../components/controls/ReplayButton";
import { HoodView } from "../../components/hood/HoodView";
import { SpeakerIcon } from "../../components/icons";
import { HoodToggle } from "../../components/layout/HoodToggle";
import { SplitPane } from "../../components/layout/SplitPane";
import { AnswerCards } from "../../components/user/AnswerCards";
import { ChatPanel } from "../../components/user/ChatPanel";
import { DeviceGrid } from "../../components/user/DeviceGrid";
import { useShortcuts } from "../../hooks/useShortcuts";
import { useSpeech } from "../../hooks/useSpeech";
import { useSpeechInput } from "../../hooks/useSpeechInput";
import { useStore } from "../../lib/store";
import { useShell } from "./shell";

function VoiceToggle() {
  const voiceOn = useStore((s) => s.voiceOn);
  const toggleVoice = useStore((s) => s.toggleVoice);
  return (
    <button
      type="button"
      onClick={toggleVoice}
      aria-pressed={voiceOn}
      aria-label="Spoken answers"
      title={voiceOn ? "Spoken answers on" : "Spoken answers off"}
      className="pressable grid h-10 w-10 place-items-center rounded-full bg-white/70 text-ink-80 hover:bg-white"
    >
      <SpeakerIcon muted={!voiceOn} size={18} />
    </button>
  );
}

/** Ask by voice or text; answers arrive as cards, with the engine view one switch away. */
export default function AssistantPage() {
  const { mode } = useShell();
  const hoodOpen = useStore((s) => s.hoodOpen);
  const [params, setParams] = useSearchParams();
  const voice = useSpeechInput();
  useSpeech();
  useShortcuts(voice);

  const question = params.get("ask")?.slice(0, 300) ?? null;
  const listen = params.has("listen");
  const clearParams = useCallback(() => setParams({}, { replace: true }), [setParams]);

  useEffect(() => {
    if (!listen) return;
    document.getElementById("voice-button")?.focus();
    voice.start();
    clearParams();
  }, [listen, clearParams, voice]);

  return (
    <>
      <div className="flex flex-wrap items-center justify-end gap-2 pb-2 sm:gap-3">
        <VoiceToggle />
        {mode === "demo" && <HoodToggle />}
        {mode === "demo" && <ReplayButton />}
      </div>
      <DemoCaption />
      <SplitPane
        hoodOpen={mode === "demo" && hoodOpen}
        left={
          <>
            <ErrorBoundary name="ask">
              <ChatPanel voice={voice} question={question} onAsked={clearParams} />
            </ErrorBoundary>
            <ErrorBoundary name="devices">
              <DeviceGrid />
            </ErrorBoundary>
            <ErrorBoundary name="answers">
              <AnswerCards />
            </ErrorBoundary>
          </>
        }
        right={mode === "demo" ?
          <ErrorBoundary name="engine">
            <HoodView />
          </ErrorBoundary>
        : null}
      />
    </>
  );
}
