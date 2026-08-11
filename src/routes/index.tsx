import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";

import { supabase } from "@/integrations/supabase/client";
import { useFrameStream } from "@/hooks/useFrameStream";
import { useHostStatus } from "@/hooks/useHostStatus";
import { CONTROL_CHANNEL, formatClock, type ControlEvent } from "@/lib/stageye";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "StagEye — remote FOH screen monitor" },
      {
        name: "description",
        content:
          "Live remote view of a front-of-house computer screen for sound engineers, with optional mouse and keyboard control.",
      },
      { property: "og:title", content: "StagEye — remote FOH screen monitor" },
      {
        property: "og:description",
        content:
          "Live remote view of a front-of-house computer screen for sound engineers, with optional mouse and keyboard control.",
      },
    ],
  }),
  component: Viewer,
});

function Viewer() {
  const { connected: framesLive, src, lastUpdate, fps } = useFrameStream();
  const { connected: hostReported } = useHostStatus();
  const connected = framesLive || hostReported;
  const [control, setControl] = useState(false);
  const [chromeVisible, setChromeVisible] = useState(true);
  const hideTimer = useRef<number | null>(null);
  const controlChannel = useRef<ReturnType<typeof supabase.channel> | null>(null);
  const lastMove = useRef(0);

  const wake = useCallback(() => {
    setChromeVisible(true);
    if (hideTimer.current) window.clearTimeout(hideTimer.current);
    hideTimer.current = window.setTimeout(() => setChromeVisible(false), 3000);
  }, []);

  useEffect(() => {
    wake();
    return () => {
      if (hideTimer.current) window.clearTimeout(hideTimer.current);
    };
  }, [wake]);

  useEffect(() => {
    if (!control) return;
    const channel = supabase.channel(CONTROL_CHANNEL);
    channel.subscribe();
    controlChannel.current = channel;

    return () => {
      controlChannel.current = null;
      supabase.removeChannel(channel);
    };
  }, [control]);

  const send = useCallback((event: ControlEvent) => {
    controlChannel.current?.send({ type: "broadcast", event: "control", payload: event });
  }, []);

  const normalize = (e: React.MouseEvent<HTMLImageElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)),
      y: Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height)),
    };
  };

  useEffect(() => {
    if (!control) return;
    const onKey = (e: KeyboardEvent) => {
      send({ type: "keydown", key: e.key });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [control, send]);

  return (
    <main
      className="relative h-screen w-screen overflow-hidden bg-background"
      onMouseMove={wake}
      onTouchStart={wake}
    >
      <div className="absolute inset-0 flex items-center justify-center">
        {src ? (
          <img
            src={src}
            alt="Live capture of the front-of-house computer screen"
            className={`max-h-full max-w-full object-contain ${control ? "cursor-crosshair" : ""}`}
            draggable={false}
            tabIndex={control ? 0 : -1}
            onMouseMove={(e) => {
              if (!control) return;
              const now = Date.now();
              if (now - lastMove.current < 100) return;
              lastMove.current = now;
              const { x, y } = normalize(e);
              send({ type: "mousemove", x, y });
            }}
            onMouseDown={(e) => {
              if (!control) return;
              e.preventDefault();
              const { x, y } = normalize(e);
              send({
                type: "mouseclick",
                x,
                y,
                button: (e.button === 1 ? 1 : e.button === 2 ? 2 : 0) as 0 | 1 | 2,
              });
            }}
            onContextMenu={(e) => control && e.preventDefault()}
          />
        ) : null}
      </div>

      {!connected ? (
        <p className="absolute top-16 left-1/2 -translate-x-1/2 text-xs tracking-widest text-muted-foreground uppercase">
          Waiting for host connection...
        </p>
      ) : null}

      <header
        className={`absolute inset-x-0 top-0 flex h-10 items-center justify-between border-b overlay-panel px-4 transition-opacity duration-500 ${
          chromeVisible ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <div className="flex items-baseline gap-3">
          <span className="text-sm font-semibold tracking-[0.2em] text-foreground">STAGEYE</span>
          <Link
            to="/host"
            className="text-[11px] tracking-widest text-muted-foreground uppercase hover:text-accent"
          >
            Host setup
          </Link>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <span>{connected ? "HOST CONNECTED" : "WAITING FOR HOST..."}</span>
          <span
            aria-hidden
            className={`size-2.5 rounded-full ${connected ? "bg-accent" : "bg-destructive"}`}
          />
        </div>
      </header>

      <footer
        className={`absolute inset-x-0 bottom-0 flex h-10 items-center justify-between border-t overlay-panel px-4 text-[11px] text-muted-foreground transition-opacity duration-500 ${
          chromeVisible ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <button
          type="button"
          onClick={() => setControl((v) => !v)}
          aria-pressed={control}
          className={`rounded border px-3 py-1 tracking-widest uppercase transition-colors ${
            control
              ? "border-accent bg-accent text-accent-foreground"
              : "border-border text-muted-foreground hover:text-foreground"
          }`}
        >
          {control ? "Control" : "View only"}
        </button>
        <div className="flex items-center gap-6">
          <span>~{fps.toFixed(fps >= 10 ? 0 : 1)} fps</span>
          <span>Updated {formatClock(lastUpdate)}</span>
        </div>
      </footer>
    </main>
  );
}
