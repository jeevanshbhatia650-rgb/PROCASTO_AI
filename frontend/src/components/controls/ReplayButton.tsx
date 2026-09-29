import { useStore } from "../../lib/store";
import { socket } from "../../lib/ws";
import { PlayIcon } from "../icons";

/** F22: the whole story in 20 seconds, through the same code path as a live microphone. */
export function ReplayButton() {
  const running = useStore((s) => s.demo !== null);
  const start = () => {
    if (!socket.send({ type: "replay.start", data: { script_id: "main_demo" } })) {
      useStore.getState().showToast("Not connected to the backend yet.");
    }
  };
  return (
    <button type="button" onClick={start} className="btn-pill py-[7px]">
      <PlayIcon size={14} />
      {running ? "Restart demo" : "Replay demo"}
    </button>
  );
}
