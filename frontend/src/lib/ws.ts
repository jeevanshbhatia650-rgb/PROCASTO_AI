import { socketUrl } from "./backend";
import type { ClientMessage, ServerMessage } from "./protocol";
import { useStore } from "./store";

const MAX_BACKOFF_MS = 5000;
const BUSY_RETRY_MS = 10_000;
const CLOSE_UNAUTHORIZED = 4401;
const CLOSE_BUSY = 1013;

/** `refresh` asks for a brand-new token (after the server said the last one was no good). */
type TokenSource = (refresh: boolean) => Promise<string | null>;

/**
 * One WebSocket per page. The first message says who we are: a signed-in user's token, or null for a demo home.
 * Reconnects with backoff; sends made while offline are dropped, not queued.
 */
class Socket {
  private ws: WebSocket | null = null;
  private backoff = 500;
  private wanted = false;
  private readonly sessionId = crypto.randomUUID();
  private token: TokenSource = async () => null;
  private requiresToken = false;
  private refreshNext = false; // one retry with a fresh token before giving up on a rejected sign-in
  private toldBusy = false;
  private onUnauthorized: () => void = () => {};

  start(token: TokenSource, onUnauthorized: () => void = () => {}, requiresToken = false): void {
    this.token = token;
    this.onUnauthorized = onUnauthorized;
    this.requiresToken = requiresToken;
    this.wanted = true;
    this.connect();
  }

  stop(): void {
    this.wanted = false;
    const ws = this.ws;
    this.ws = null;
    ws?.close();
    useStore.getState().clearPrivate();
  }

  /** New session, e.g. after an account was connected or removed. */
  restart(): void {
    const ws = this.ws;
    this.ws = null;
    ws?.close();
    useStore.getState().clearPrivate();
    if (this.wanted) this.connect();
  }

  private connect(): void {
    if (this.ws && this.ws.readyState !== WebSocket.CLOSED) return; // StrictMode runs effects twice
    const ws = new WebSocket(socketUrl(`/ws/session/${this.sessionId}`));
    this.ws = ws;
    useStore.getState().setConnection("connecting");
    ws.onopen = async () => {
      let token: string | null;
      try {
        token = await this.token(this.refreshNext);
      } catch {
        ws.close(1013, "sign-in check unavailable");
        return;
      }
      if (this.ws !== ws || ws.readyState !== WebSocket.OPEN) return;
      if (this.requiresToken && !token) {
        ws.close(CLOSE_UNAUTHORIZED, "sign in again");
        return;
      }
      ws.send(JSON.stringify({ type: "auth", data: { token } } satisfies ClientMessage));
      useStore.getState().setConnection("open");
    };
    ws.onmessage = (event) => {
      if (this.ws !== ws) return;
      const message = JSON.parse(event.data) as ServerMessage;
      if (message.type === "hello") {
        // Only a hello proves the server took us: until then, a server that keeps refusing gets slower retries.
        this.backoff = 500;
        this.refreshNext = this.toldBusy = false;
      }
      useStore.getState().apply(message);
    };
    ws.onclose = (event) => {
      if (this.ws !== ws) return;
      this.ws = null;
      useStore.getState().setConnection("closed");
      if (event.code === CLOSE_UNAUTHORIZED) {
        if (this.refreshNext) return this.onUnauthorized();
        this.refreshNext = true; // maybe just an old token: try once more with a fresh one
      }
      if (!this.wanted) return;
      let delay = this.backoff;
      if (event.code === CLOSE_BUSY) {
        delay = BUSY_RETRY_MS;
        if (event.reason && !this.toldBusy) useStore.getState().showToast(event.reason);
        this.toldBusy = true;
      }
      setTimeout(() => this.wanted && this.connect(), delay);
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
