import { useState } from "react";

type CopyBlockProps = {
  label: string;
  value: string;
  masked?: boolean;
};

/** Monospace code block with a copy button, used for host configuration values. */
export function CopyBlock({ label, value, masked = false }: CopyBlockProps) {
  const [copied, setCopied] = useState(false);
  const [revealed, setRevealed] = useState(!masked);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="space-y-2">
      <p className="text-[11px] tracking-widest text-muted-foreground uppercase">{label}</p>
      <div className="flex items-stretch gap-2">
        <code className="flex-1 overflow-x-auto rounded border border-border bg-panel px-3 py-2 text-xs break-all text-accent">
          {revealed ? value : "•".repeat(48)}
        </code>
        {masked && !revealed ? (
          <button
            type="button"
            onClick={() => setRevealed(true)}
            className="rounded border border-border px-3 text-[11px] tracking-widest uppercase hover:text-foreground"
          >
            Show
          </button>
        ) : null}
        <button
          type="button"
          onClick={copy}
          className="rounded border border-border px-3 text-[11px] tracking-widest uppercase hover:border-accent hover:text-accent"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}
