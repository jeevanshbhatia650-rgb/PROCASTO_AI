import { sendTranscript } from "./ws";

/**
 * Plays a question in word by word at speaking pace, sending a partial transcript after every word,
 * exactly like the microphone does. Returns a cancel function.
 */
export function typeOut(text: string, onText: (partial: string) => void, msPerWord = 230): () => void {
  const words = text.trim().split(/\s+/);
  let count = 0;
  let timer = 0;
  const step = () => {
    count += 1;
    const partial = words.slice(0, count).join(" ");
    onText(partial);
    sendTranscript(partial, false);
    timer = window.setTimeout(count < words.length ? step : finish, msPerWord);
  };
  const finish = () => {
    sendTranscript(words.join(" "), true);
    onText("");
  };
  timer = window.setTimeout(step, 0);
  return () => window.clearTimeout(timer);
}
