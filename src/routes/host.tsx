import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";

import { useFrameStream } from "@/hooks/useFrameStream";
import { useHostStatus } from "@/hooks/useHostStatus";
import { SUPABASE_ANON_KEY, SUPABASE_URL, formatClock } from "@/lib/stageye";

export const Route = createFileRoute("/host")({
  head: () => ({
    meta: [
      { title: "Host setup — StagEye" },
      {
        name: "description",
        content:
          "Configure the StagEye host capture script on your front-of-house computer and check its connection status.",
      },
      { property: "og:title", content: "Host setup — StagEye" },
      {
        property: "og:description",
        content:
          "Configure the StagEye host capture script on your front-of-house computer and check its connection status.",
      },
    ],
  }),
  component: HostPage,
});

const script = `# stageye_host.py - run on the FOH computer
# pip install mss pillow supabase pynput
import io, time, asyncio
from mss import mss
from PIL import Image
from supabase import create_client
from pynput.mouse import Button, Controller as Mouse
from pynput.keyboard import Controller as Keyboard

SUPABASE_URL = "<project url above>"
SUPABASE_KEY = "<anon key above>"
sb = create_client(SUPABASE_URL, SUPABASE_KEY)
mouse, keyboard = Mouse(), Keyboard()
BUTTONS = {0: Button.left, 1: Button.middle, 2: Button.right}

async def main():
    frames = sb.realtime.channel("frame-updates")
    await frames.subscribe()

    control = sb.realtime.channel("control-events")

    def on_control(payload):
        e = payload.get("payload", payload)
        w, h = mouse_screen
        if e["type"] in ("mousemove", "mouseclick"):
            mouse.position = (int(e["x"] * w), int(e["y"] * h))
        if e["type"] == "mouseclick":
            mouse.click(BUTTONS.get(e.get("button", 0), Button.left))
        elif e["type"] == "keydown":
            keyboard.type(e["key"]) if len(e["key"]) == 1 else None

    control.on_broadcast("control", on_control)
    await control.subscribe()

    with mss() as sct:
        mon = sct.monitors[1]
        globals()["mouse_screen"] = (mon["width"], mon["height"])
        last_beat = 0.0
        try:
            while True:
                shot = sct.grab(mon)
                img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=55)
                sb.storage.from_("screen-frames").upload(
                    "latest.jpg", buf.getvalue(),
                    {"content-type": "image/jpeg", "upsert": "true", "cache-control": "0"},
                )
                await frames.send_broadcast("frame", {"timestamp": int(time.time() * 1000)})

                # Heartbeat every 5 seconds so viewers see "Host connected"
                if time.time() - last_beat >= 5:
                    last_beat = time.time()
                    sb.table("host_status").update({
                        "is_connected": True,
                        "last_seen_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", 1).execute()

                await asyncio.sleep(1)
        finally:
            sb.table("host_status").update({"is_connected": False}).eq("id", 1).execute()

asyncio.run(main())`;



function HostPage() {
  const { lastUpdate, fps } = useFrameStream();
  const { connected } = useHostStatus();
  const [revealed, setRevealed] = useState(false);

  return (
    <main className="min-h-screen bg-background px-6 py-10">
      <div className="mx-auto max-w-3xl space-y-8">
        <header className="flex items-center justify-between border-b border-border pb-4">
          <div>
            <h1 className="text-lg font-semibold tracking-[0.2em]">STAGEYE / HOST</h1>
            <p className="mt-1 text-xs text-muted-foreground">
              Capture setup for the front-of-house computer
            </p>
          </div>
          <Link to="/" className="text-xs text-muted-foreground hover:text-accent">
            Open viewer
          </Link>
        </header>

        <section className="rounded-md border border-border bg-panel p-4">
          <div className="flex items-center gap-2">
            <span
              aria-hidden
              className={`size-2.5 rounded-full ${connected ? "bg-accent" : "bg-destructive"}`}
            />
            <h2 className="text-sm">{connected ? "Host connected" : "Host disconnected"}</h2>
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-xs text-muted-foreground">
            <div>
              <dt>Frame rate</dt>
              <dd className="text-foreground">~{fps.toFixed(fps >= 10 ? 0 : 1)} fps</dd>
            </div>
            <div>
              <dt>Last frame</dt>
              <dd className="text-foreground">{formatClock(lastUpdate)}</dd>
            </div>
          </dl>
        </section>

        <section className="space-y-3">
          <h2 className="text-sm tracking-widest uppercase">Connection details</h2>
          <div className="space-y-2 rounded-md border border-border bg-panel p-4 text-xs">
            <p className="text-muted-foreground">Project URL</p>
            <code className="block break-all text-accent">{SUPABASE_URL}</code>
            <p className="pt-2 text-muted-foreground">Anon key (safe to use in the script)</p>
            {revealed ? (
              <code className="block break-all text-accent">{SUPABASE_ANON_KEY}</code>
            ) : (
              <button
                type="button"
                onClick={() => setRevealed(true)}
                className="rounded border border-border px-3 py-1 tracking-widest uppercase hover:text-foreground"
              >
                Reveal key
              </button>
            )}
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-sm tracking-widest uppercase">Running the host script</h2>
          <ol className="list-decimal space-y-1 pl-5 text-xs text-muted-foreground">
            <li>Install Python 3.10 or newer on the FOH computer.</li>
            <li>
              Install dependencies: <code className="text-accent">pip install mss pillow supabase pynput</code>
            </li>
            <li>Paste the script below, filling in the project URL and anon key above.</li>
            <li>
              Run it: <code className="text-accent">python stageye_host.py</code>
            </li>
            <li>
              It uploads <code className="text-accent">latest.jpg</code> to the{" "}
              <code className="text-accent">screen-frames</code> bucket, broadcasts{" "}
              <code className="text-accent">{"{ timestamp }"}</code> on{" "}
              <code className="text-accent">frame-updates</code>, and applies incoming events from{" "}
              <code className="text-accent">control-events</code>.
            </li>
          </ol>
          <pre className="overflow-x-auto rounded-md border border-border bg-panel p-4 text-[11px] leading-relaxed text-foreground">
            <code>{script}</code>
          </pre>
        </section>
      </div>
    </main>
  );
}
