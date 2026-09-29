import type { ClientMessage, ServerMessage } from "./protocol";
import { useStore } from "./store";

const MAX_BACKOFF_MS = 5000;

/** One WebSocket per page. Reconnects with backoff; sends made while offline are dropped, not queued. */
class Socket {
  private ws: WebSocket | null = null;
  private backoff = 500;
  private readonly sessionId = crypto.randomUUID();

  connect(): void {
    if (this.ws && this.ws.readyState !== WebSocket.CLOSED) return; // StrictMode runs effects twice
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${scheme}://${location.host}/ws/session/${this.sessionId}`);
    this.ws = ws;
    useStore.getState().setConnection("connecting");
    ws.onopen = () => {
      this.backoff = 500;
      useStore.getState().setConnection("open");
    };
    ws.onmessage = (event) => useStore.getState().apply(JSON.parse(event.data) as ServerMessage);
    ws.onclose = () => {
      if (this.ws !== ws) return;
      useStore.getState().setConnection("closed");
      setTimeout(() => this.connect(), this.backoff);
      this.backoff = Math.min(this.backoff * 2, MAX_BACKOFF_MS);
    };
  }

  send(message: ClientMessage): boolean {
    if (this.ws?.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify(message));
    return true;
  }
}

export const socket = new Socket();

let seq = 0;

export function sendTranscript(text: string, final: boolean): void {
  socket.send({ type: final ? "transcript.final" : "transcript.partial", data: { text, seq: ++seq } });
}
