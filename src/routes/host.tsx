import { createFileRoute, Link } from "@tanstack/react-router";
import { useFrameStream } from "@/hooks/useFrameStream";
import { useHostStatus } from "@/hooks/useHostStatus";
import { CopyBlock } from "@/components/CopyBlock";
import { PIP_INSTALL, SUPABASE_ANON_KEY, SUPABASE_URL, formatClock } from "@/lib/stageye";

export const Route = createFileRoute("/host")({
  head: () => ({
    meta: [
      { title: "Host setup — Stageye" },
      {
        name: "description",
        content:
          "Configure the StagEye host capture script on your front-of-house computer and check its connection status.",
      },
      { property: "og:title", content: "Host setup — Stageye" },
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
# pip install mss pillow supabase pyautogui
import io, time, asyncio
from datetime import datetime, timezone
from mss import mss
from PIL import Image
from supabase import create_client
import pyautogui

pyautogui.FAILSAFE = False

SUPABASE_URL = "<project url above>"
SUPABASE_KEY = "<anon key above>"
sb = create_client(SUPABASE_URL, SUPABASE_KEY)
BUTTONS = {0: "left", 1: "middle", 2: "right"}

async def main():
    frames = sb.realtime.channel("frame-updates")
    await frames.subscribe()

    control = sb.realtime.channel("control-events")

    def on_control(payload):
        e = payload.get("payload", payload)
        w, h = screen_size
        if e["type"] in ("mousemove", "mouseclick"):
            pyautogui.moveTo(int(e["x"] * w), int(e["y"] * h))
        if e["type"] == "mouseclick":
            pyautogui.click(button=BUTTONS.get(e.get("button", 0), "left"))
        elif e["type"] == "keydown":
            key = e["key"]
            pyautogui.press({"Enter": "enter", "Escape": "esc", " ": "space"}.get(key, key.lower()))


    control.on_broadcast("control", on_control)
    await control.subscribe()

    with mss() as sct:
        mon = sct.monitors[1]
        globals()["screen_size"] = (mon["width"], mon["height"])
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
          <div className="space-y-4 rounded-md border border-border bg-panel p-4">
            <CopyBlock label="Project URL" value={SUPABASE_URL} />
            <CopyBlock label="Anon key" value={SUPABASE_ANON_KEY} masked />
            <CopyBlock label="Install dependencies" value={PIP_INSTALL} />
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-sm tracking-widest uppercase">Running the host script</h2>
          <ol className="list-decimal space-y-1 pl-5 text-xs text-muted-foreground">
            <li>Install Python 3.10 or newer on the FOH computer.</li>
            <li>Install the dependencies with the command above.</li>
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
            <li>
              Autostart on Windows: press <code className="text-accent">Win + R</code>, run{" "}
              <code className="text-accent">shell:startup</code>, and drop a shortcut to{" "}
              <code className="text-accent">stageye_host.py</code> (or a{" "}
              <code className="text-accent">.bat</code> that calls it) in that folder so the host
              script starts automatically on boot.
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
