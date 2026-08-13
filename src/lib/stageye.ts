export const FRAME_BUCKET = "screen-frames";
export const FRAME_OBJECT = "latest.jpg";
export const FRAME_CHANNEL = "frame-updates";
export const CONTROL_CHANNEL = "control-events";

/** Default room — used when no ?room= is in the URL. */
export const DEFAULT_ROOM = "default";

/** Storage path for a room's latest frame. */
export function roomFrameObject(room: string): string {
  return `${room}/latest.jpg`;
}

/** Realtime channel for a room's frame notifications. */
export function roomFrameChannel(room: string): string {
  return `${FRAME_CHANNEL}-${room}`;
}

/** Realtime channel for a room's control events. */
export function roomControlChannel(room: string): string {
  return `${CONTROL_CHANNEL}-${room}`;
}

/** Milliseconds without a frame notification before the host is considered offline. */
export const HOST_TIMEOUT_MS = 5000;

/** Milliseconds since host_status.last_seen_at before the host counts as offline. */
export const HOST_STALE_MS = 10000;

export const SUPABASE_URL =
  (import.meta.env["VITE_SUPABASE_URL"] as string | undefined) ?? "";
export const SUPABASE_ANON_KEY =
  (import.meta.env["VITE_SUPABASE_ANON_KEY"] as string | undefined) ??
  (import.meta.env["VITE_SUPABASE_PUBLISHABLE_KEY"] as string | undefined) ??
  "";

export const PIP_INSTALL = "pip install mss pillow supabase pyautogui";

export function frameUrl(timestamp: number): string {
  return `${SUPABASE_URL}/storage/v1/object/public/${FRAME_BUCKET}/${FRAME_OBJECT}?t=${timestamp}`;
}

/** Full public URL for a room's latest frame with cache-busting timestamp. */
export function roomFrameUrl(room: string, timestamp: number): string {
  return `${SUPABASE_URL}/storage/v1/object/public/${FRAME_BUCKET}/${roomFrameObject(room)}?t=${timestamp}`;
}

export type ControlEvent =
  | { type: "mousemove"; x: number; y: number }
  | { type: "mouseclick"; x: number; y: number; button: 0 | 1 | 2 }
  | { type: "keydown"; key: string };

export function formatClock(ms: number | null): string {
  if (!ms) return "--:--:--";
  return new Date(ms).toLocaleTimeString(undefined, { hour12: false });
}
