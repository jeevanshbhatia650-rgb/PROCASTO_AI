import { MotionConfig } from "motion/react";
import { useEffect } from "react";
import { Toaster, toast } from "sonner";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ChaosPanel } from "./components/controls/ChaosPanel";
import { DemoCaption } from "./components/controls/DemoCaption";
import { HoodView } from "./components/hood/HoodView";
import { Header } from "./components/layout/Header";
import { SplitPane } from "./components/layout/SplitPane";
import { AnswerCards } from "./components/user/AnswerCards";
import { ChatPanel } from "./components/user/ChatPanel";
import { DeviceGrid } from "./components/user/DeviceGrid";
import { useShortcuts } from "./hooks/useShortcuts";
import { useSpeech } from "./hooks/useSpeech";
import { useSpeechInput } from "./hooks/useSpeechInput";
import { useStore } from "./lib/store";
import { socket } from "./lib/ws";

function useToasts(): void {
  const message = useStore((s) => s.toast);
  useEffect(() => {
    if (message) toast(message.message);
  }, [message]);
}

export default function App() {
  const hoodOpen = useStore((s) => s.hoodOpen);
  const voice = useSpeechInput();
  useEffect(() => socket.connect(), []);
  useSpeech();
  useShortcuts(voice);
  useToasts();

  return (
    <MotionConfig reducedMotion="user">
      <div className="min-h-dvh pb-28">
        <Header />
        <DemoCaption />
        <main className="mx-auto max-w-[1440px] px-4 md:px-6">
          <SplitPane
            hoodOpen={hoodOpen}
            left={
              <>
                <ErrorBoundary name="ask">
                  <ChatPanel voice={voice} />
                </ErrorBoundary>
                <ErrorBoundary name="devices">
                  <DeviceGrid />
                </ErrorBoundary>
                <ErrorBoundary name="answers">
                  <AnswerCards />
                </ErrorBoundary>
              </>
            }
            right={
              <ErrorBoundary name="engine">
                <HoodView />
              </ErrorBoundary>
            }
          />
        </main>
        <ChaosPanel />
        <Toaster position="top-center" offset={112} toastOptions={{ className: "t-caption" }} />
      </div>
    </MotionConfig>
  );
}
