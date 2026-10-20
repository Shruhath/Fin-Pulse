/**
 * Recording a spoken question in the browser. The audio is turned into 16 kHz mono WAV here and sent to the
 * local API, which transcribes it on the same machine; the browser's own speech recognition is not used
 * because it sends audio to a third party.
 */

import { useSyncExternalStore } from "react";

const SAMPLE_RATE = 16_000;
const FRAME_MS = 60;

export const voiceSupported = () =>
  typeof window !== "undefined" &&
  window.isSecureContext &&
  !!navigator.mediaDevices?.getUserMedia &&
  typeof MediaRecorder !== "undefined" &&
  typeof AudioContext !== "undefined";

const never = () => () => {};

/** Whether this browser and page can record; false while the server renders, so the first paint matches it. */
export const useVoiceSupported = () => useSyncExternalStore(never, voiceSupported, () => false);

export interface Listener {
  /** End the recording now and use what was said. */
  stop: () => void;
  /** End the recording and throw it away. */
  cancel: () => void;
  /** The recording as WAV, or null when nothing was said or it was cancelled. */
  result: Promise<Blob | null>;
}

interface Options {
  /** 0 to 1, about every 60 ms, for a level meter */
  onLevel?: (level: number) => void;
  /** stop this long after the last speech */
  silenceMs?: number;
  /** give up if nothing is said within this time */
  noSpeechMs?: number;
  maxMs?: number;
}

export function describeMicError(e: unknown): string {
  const name = e instanceof DOMException ? e.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "Microphone access is blocked. Allow it for this site in the browser's settings, then try again.";
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") return "No microphone was found.";
  if (name === "NotReadableError") return "The microphone is in use by another program.";
  return e instanceof Error ? e.message : "The microphone could not be started.";
}

/** Start listening. Ends by itself after a pause in speech, so a question needs one click, not two. */
export async function listen({ onLevel, silenceMs = 1500, noSpeechMs = 8000, maxMs = 30_000 }: Options = {}): Promise<Listener> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  const recorder = new MediaRecorder(stream);
  const chunks: Blob[] = [];
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  const ctx = new AudioContext();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  ctx.createMediaStreamSource(stream).connect(analyser);
  const frame = new Float32Array(analyser.fftSize);

  let heard = false;
  let cancelled = false;
  let finished = false;
  const started = performance.now();
  let lastVoice = started;
  const floor: number[] = [];

  let resolveResult!: (b: Blob | null) => void;
  const result = new Promise<Blob | null>((r) => {
    resolveResult = r;
  });

  const finish = () => {
    if (finished) return;
    finished = true;
    clearInterval(timer);
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      void ctx.close();
      onLevel?.(0);
      if (cancelled || !heard || chunks.length === 0) return resolveResult(null);
      try {
        resolveResult(await toWav16k(new Blob(chunks, { type: recorder.mimeType })));
      } catch {
        resolveResult(null);
      }
    };
    if (recorder.state !== "inactive") recorder.stop();
    else recorder.onstop?.(new Event("stop"));
  };

  const timer = setInterval(() => {
    analyser.getFloatTimeDomainData(frame);
    let sum = 0;
    for (const v of frame) sum += v * v;
    const rms = Math.sqrt(sum / frame.length);
    onLevel?.(Math.min(1, rms * 8));
    const now = performance.now();
    // the quietest of the first few frames is the room's noise; speech has to stand clearly above it
    if (floor.length < 5) floor.push(rms);
    const noise = [...floor].sort((a, b) => a - b)[0] ?? 0;
    const threshold = Math.min(0.04, Math.max(0.015, noise * 2));
    if (rms > threshold) {
      heard = true;
      lastVoice = now;
    }
    if (heard && now - lastVoice > silenceMs) finish();
    else if (!heard && now - started > noSpeechMs) finish();
    else if (now - started > maxMs) finish();
  }, FRAME_MS);

  recorder.start(250);
  return {
    stop: finish,
    cancel: () => {
      cancelled = true;
      finish();
    },
    result,
  };
}

/** Decode a recording, mix it to mono, resample to 16 kHz and write it as 16-bit PCM WAV. */
export async function toWav16k(recording: Blob): Promise<Blob> {
  const decoder = new AudioContext();
  try {
    const decoded = await decoder.decodeAudioData(await recording.arrayBuffer());
    const offline = new OfflineAudioContext(1, Math.max(1, Math.ceil(decoded.duration * SAMPLE_RATE)), SAMPLE_RATE);
    const source = offline.createBufferSource();
    source.buffer = decoded;
    source.connect(offline.destination);
    source.start();
    const rendered = await offline.startRendering();
    return encodeWav(rendered.getChannelData(0), SAMPLE_RATE);
  } finally {
    void decoder.close();
  }
}

export function encodeWav(samples: Float32Array, rate: number): Blob {
  const view = new DataView(new ArrayBuffer(44 + samples.length * 2));
  const text = (at: number, s: string) => [...s].forEach((c, i) => view.setUint8(at + i, c.charCodeAt(0)));
  text(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVEfmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((s, i) => view.setInt16(44 + i * 2, Math.round(Math.max(-1, Math.min(1, s)) * 32767), true));
  return new Blob([view], { type: "audio/wav" });
}
