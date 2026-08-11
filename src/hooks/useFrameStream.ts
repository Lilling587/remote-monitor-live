import { useEffect, useRef, useState } from "react";

import { supabase } from "@/integrations/supabase/client";
import { FRAME_CHANNEL, HOST_TIMEOUT_MS, frameUrl } from "@/lib/stageye";

export type FrameStream = {
  connected: boolean;
  src: string | null;
  lastUpdate: number | null;
  fps: number;
};

export function useFrameStream(): FrameStream {
  const [src, setSrc] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);
  const [fps, setFps] = useState(0);
  const [connected, setConnected] = useState(false);
  const stamps = useRef<number[]>([]);

  useEffect(() => {
    const channel = supabase
      .channel(FRAME_CHANNEL)
      .on("broadcast", { event: "frame" }, (payload) => {
        const raw = (payload as { payload?: { timestamp?: number } }).payload?.timestamp;
        const timestamp = typeof raw === "number" ? raw : Date.now();
        const now = Date.now();

        setSrc(frameUrl(timestamp));
        setLastUpdate(now);
        setConnected(true);

        stamps.current = [...stamps.current, now].filter((t) => now - t < 5000);
        const first = stamps.current[0];
        const span = first === undefined ? 0 : now - first;
        setFps(stamps.current.length > 1 && span > 0 ? ((stamps.current.length - 1) / span) * 1000 : 0);
      })
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setLastUpdate((current) => {
        if (current !== null && Date.now() - current > HOST_TIMEOUT_MS) {
          setConnected(false);
          setFps(0);
        }
        return current;
      });
    }, 1000);

    return () => window.clearInterval(interval);
  }, []);

  return { connected, src, lastUpdate, fps };
}
