export const FRAME_BUCKET = "screen-frames";

/** Default room — used when no ?room= is in the URL. */
export const DEFAULT_ROOM = "stora-salen";

/** Storage path for a room's latest frame. */
export function roomFrameObject(room: string): string {
  return `${room}/latest.jpg`;
}

/** How old the stored frame may be before the host counts as offline. */
export const HOST_TIMEOUT_MS = 12000;

export const SUPABASE_URL =
  (import.meta.env["VITE_SUPABASE_URL"] as string | undefined) ?? "";

export const SUPABASE_ANON_KEY =
  (import.meta.env["VITE_SUPABASE_ANON_KEY"] as string | undefined) ??
  (import.meta.env["VITE_SUPABASE_PUBLISHABLE_KEY"] as string | undefined) ??
  "";

export const PIP_INSTALL = "pip install mss pillow requests pyautogui";

/** Full public URL for a room's latest frame with cache-busting timestamp. */
export function roomFrameUrl(room: string, timestamp: number): string {
  return `${SUPABASE_URL}/storage/v1/object/public/${FRAME_BUCKET}/${roomFrameObject(room)}?t=${timestamp}`;
}

export function formatClock(ms: number | null): string {
  if (!ms) return "--:--:--";
  return new Date(ms).toLocaleTimeString(undefined, { hour12: false });
}
