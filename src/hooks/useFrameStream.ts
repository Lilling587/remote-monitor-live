import { useEffect, useState } from "react";
import { HOST_TIMEOUT_MS, roomFrameUrl } from "@/lib/stageye";

export type FrameStream = {
  connected: boolean;
  src: string | null;
  lastUpdate: number | null;
  fps: number;
};

/** Hur ofta vi frågar efter en ny bild. Matchar CLOUD_INTERVAL i stageye_host.py. */
const POLL_INTERVAL_MS = 2000;

export function useFrameStream(room: string): FrameStream {
  const [src, setSrc] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);
  const [fps, setFps] = useState(0);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    let objectUrl: string | null = null;
    let lastModified = 0;
    let stamps: number[] = [];

    async function tick() {
      try {
        const response = await fetch(roomFrameUrl(room, Date.now()), {
          cache: "no-store",
        });
        if (!response.ok) throw new Error(String(response.status));

        const header = response.headers.get("last-modified");
        const modified = header ? Date.parse(header) : Date.now();
        const blob = await response.blob();
        if (cancelled) return;

        const fresh = Date.now() - modified < HOST_TIMEOUT_MS;
        setConnected(fresh);
        if (!fresh) setFps(0);

        if (modified !== lastModified) {
          lastModified = modified;

          const next = URL.createObjectURL(blob);
          if (objectUrl) URL.revokeObjectURL(objectUrl);
          objectUrl = next;

          setSrc(next);
          setLastUpdate(modified);

          const now = Date.now();
          stamps = [...stamps, now].filter((t) => now - t < 10000);
          const first = stamps[0];
          const span = first === undefined ? 0 : now - first;
          setFps(
            stamps.length > 1 && span > 0
              ? ((stamps.length - 1) / span) * 1000
              : 0,
          );
        }
      } catch {
        if (!cancelled) {
          setConnected(false);
          setFps(0);
        }
      } finally {
        if (!cancelled) {
          timer = window.setTimeout(tick, POLL_INTERVAL_MS);
        }
      }
    }

    void tick();

    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [room]);

  return { connected, src, lastUpdate, fps };
}
