import { useEffect, useState } from "react";

import { supabase } from "@/integrations/supabase/client";
import { HOST_STALE_MS } from "@/lib/stageye";

export type HostStatus = {
  /** True when the host reported itself connected within the stale window. */
  connected: boolean;
  lastSeenAt: number | null;
};

function isFresh(lastSeenAt: number | null, isConnected: boolean): boolean {
  if (!isConnected || lastSeenAt === null) return false;
  return Date.now() - lastSeenAt < HOST_STALE_MS;
}

export function useHostStatus(): HostStatus {
  const [lastSeenAt, setLastSeenAt] = useState<number | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [, setTick] = useState(0);

  useEffect(() => {
    let active = true;

    const apply = (row: { last_seen_at: string | null; is_connected: boolean } | null) => {
      if (!active || !row) return;
      setLastSeenAt(row.last_seen_at ? new Date(row.last_seen_at).getTime() : null);
      setIsConnected(row.is_connected);
    };

    void supabase
      .from("host_status")
      .select("last_seen_at, is_connected")
      .eq("id", 1)
      .maybeSingle()
      .then(({ data }) => apply(data));

    const channel = supabase
      .channel("host-status")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "host_status" },
        (payload) => {
          apply(payload.new as { last_seen_at: string | null; is_connected: boolean });
        },
      )
      .subscribe();

    return () => {
      active = false;
      supabase.removeChannel(channel);
    };
  }, []);

  // Re-evaluate freshness once per second so a silent host goes offline.
  useEffect(() => {
    const interval = window.setInterval(() => setTick((t) => t + 1), 1000);
    return () => window.clearInterval(interval);
  }, []);

  return { connected: isFresh(lastSeenAt, isConnected), lastSeenAt };
}
