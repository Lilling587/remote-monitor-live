import { createFileRoute, Link } from "@tanstack/react-router";
import { useFrameStream } from "@/hooks/useFrameStream";
import { CopyBlock } from "@/components/CopyBlock";
import {
  DEFAULT_ROOM,
  PIP_INSTALL,
  SUPABASE_ANON_KEY,
  SUPABASE_URL,
  formatClock,
} from "@/lib/stageye";

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

const SCRIPT_URL =
  "https://github.com/Lilling587/remote-monitor-live/blob/main/stageye_host.py";

const FIREWALL_CMD =
  'netsh advfirewall firewall add rule name="StagEye LAN" dir=in action=allow protocol=TCP localport=8080';

function HostPage() {
  const { connected, lastUpdate, fps } = useFrameStream(DEFAULT_ROOM);

  return (
    <main className="min-h-screen bg-background px-6 py-10">
      <div className="mx-auto max-w-3xl space-y-8">
        <header className="flex items-center justify-between border-b border-border pb-4">
          <div>
            <h1 className="text-lg font-semibold tracking-[0.2em]">
              STAGEYE / HOST
              <span className="sr-only"> — Host Setup &amp; Configuration</span>
            </h1>
            <p className="mt-1 text-xs text-zinc-400">
              Capture setup for the front-of-house computer
            </p>
          </div>
          <Link to="/" search={{ room: DEFAULT_ROOM }} className="text-xs text-zinc-400 hover:text-accent">
            Open viewer
          </Link>
        </header>

        <section className="rounded-md border border-border bg-panel p-4">
          <div className="flex items-center gap-2">
            <span
              aria-hidden
              className={`size-2.5 rounded-full ${connected ? "bg-accent" : "bg-destructive"}`}
            />
            <h2 className="text-sm">
              {connected ? "Host connected" : "Host disconnected"}
            </h2>
            <span className="text-xs text-zinc-500">({DEFAULT_ROOM})</span>
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-xs text-zinc-400">
            <div>
              <dt>Frame rate</dt>
              <dd className="text-foreground">
                ~{fps.toFixed(fps >= 10 ? 0 : 1)} fps
              </dd>
            </div>
            <div>
              <dt>Last frame</dt>
              <dd className="text-foreground">{formatClock(lastUpdate)}</dd>
            </div>
          </dl>
          <p className="mt-3 text-xs text-zinc-500">
            Status is derived from how recently the frame in storage was
            written. A stale frame means the host script is not uploading.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-sm tracking-widest uppercase">
            Connection details
          </h2>
          <div className="space-y-4 rounded-md border border-border bg-panel p-4">
            <CopyBlock label="Project URL" value={SUPABASE_URL} />
            <CopyBlock label="Publishable key" value={SUPABASE_ANON_KEY} masked />
            <CopyBlock label="Install dependencies" value={PIP_INSTALL} />
            <CopyBlock label="Open LAN port (run as admin)" value={FIREWALL_CMD} />
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-sm tracking-widest uppercase">
            Setting up a host computer
          </h2>
          <ol className="list-decimal space-y-2 pl-5 text-xs text-zinc-300">
            <li>
              Install Python 3.12. Do not use 3.14 — it has no prebuilt wheels
              for <code className="text-accent">mss</code>.
            </li>
            <li>Install the dependencies with the command above.</li>
            <li>
              Download{" "}
              <a
                href={SCRIPT_URL}
                className="text-accent underline"
                target="_blank"
                rel="noreferrer"
              >
                stageye_host.py
              </a>{" "}
              from the repository. Always take the current version from there —
              never copy it from this page.
            </li>
            <li>
              Open the file and set <code className="text-accent">ROOM</code> and{" "}
              <code className="text-accent">ROOM_LABEL</code> to match the stage
              this computer belongs to.
            </li>
            <li>Run the firewall command above once, as administrator.</li>
            <li>
              Start it: <code className="text-accent">py -3.12 stageye_host.py</code>.
              The log file <code className="text-accent">stageye_host.log</code>{" "}
              appears next to the script and prints the LAN address to open on a
              phone.
            </li>
            <li>
              Autostart on Windows: press <code className="text-accent">Win + R</code>,
              run <code className="text-accent">shell:startup</code>, and place a
              shortcut to <code className="text-accent">stageye_start.bat</code>{" "}
              in that folder.
            </li>
          </ol>
        </section>

        <section className="space-y-3">
          <h2 className="text-sm tracking-widest uppercase">How it works</h2>
          <p className="text-xs leading-relaxed text-zinc-400">
            The script captures the screen continuously. Each frame is served
            from a small web server on the FOH computer, which any phone on the
            same network can open without internet access, and is also uploaded
            to Supabase Storage for remote viewing. If the upload fails, local
            viewing is unaffected.
          </p>
        </section>
      </div>
    </main>
  );
}
