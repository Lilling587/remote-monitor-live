import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { useFrameStream } from "@/hooks/useFrameStream";
import { DEFAULT_ROOM, formatClock } from "@/lib/stageye";

export const Route = createFileRoute("/")({
  validateSearch: (search: Record<string, unknown>): { room: string } => {
    const room = search["room"];
    return {
      room: typeof room === "string" && room.length > 0 ? room : DEFAULT_ROOM,
    };
  },
  head: () => ({
    meta: [
      { title: "Stageye - remote screen monitor" },
      {
        name: "description",
        content: "Live remote view of a front-of-house computer screen",
      },
      { property: "og:title", content: "Stageye - remote screen monitor" },
      {
        property: "og:description",
        content: "Live remote view of a front-of-house computer screen",
      },
    ],
  }),
  component: Viewer,
});

function Viewer() {
  const { room } = Route.useSearch();
  const { connected, src, lastUpdate, fps } = useFrameStream(room);

  const [chromeVisible, setChromeVisible] = useState(true);
  const hideTimer = useRef<number | null>(null);

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
            className="max-h-full max-w-full object-contain"
            draggable={false}
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
          <h1 className="text-sm font-semibold tracking-[0.2em] text-foreground">
            STAGEYE
            <span className="sr-only"> — Remote Screen Monitor</span>
          </h1>
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
        <span className="tracking-widest uppercase">{room}</span>
        <div className="flex items-center gap-6">
          <span>~{fps.toFixed(fps >= 10 ? 0 : 1)} fps</span>
          <span>Updated {formatClock(lastUpdate)}</span>
        </div>
      </footer>
    </main>
  );
}
