export const FRAME_BUCKET = "screen-frames";
export const FRAME_OBJECT = "latest.jpg";
export const FRAME_CHANNEL = "frame-updates";
export const CONTROL_CHANNEL = "control-events";

/** Milliseconds without a frame notification before the host is considered offline. */
export const HOST_TIMEOUT_MS = 5000;

export const SUPABASE_URL =
  (import.meta.env["VITE_SUPABASE_URL"] as string | undefined) ?? "";
export const SUPABASE_ANON_KEY =
  (import.meta.env["VITE_SUPABASE_PUBLISHABLE_KEY"] as string | undefined) ?? "";

export function frameUrl(timestamp: number): string {
  return `${SUPABASE_URL}/storage/v1/object/public/${FRAME_BUCKET}/${FRAME_OBJECT}?t=${timestamp}`;
}

export type ControlEvent = {
  type: "mousemove" | "mouseclick" | "keydown";
  x: number;
  y: number;
  button: 0 | 1 | 2;
  key: string;
};

export function formatClock(ms: number | null): string {
  if (!ms) return "--:--:--";
  return new Date(ms).toLocaleTimeString(undefined, { hour12: false });
}
