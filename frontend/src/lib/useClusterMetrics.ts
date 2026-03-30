"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { MetricsSnapshot, CpuHistoryPoint } from "@/lib/types/metrics";

const HISTORY_LIMIT = 30;          // last N points kept per node
const BASE_RECONNECT_MS = 2_000;   // start at 2 s
const MAX_RECONNECT_MS  = 30_000;  // cap at 30 s

export type WSStatus = "connecting" | "connected" | "reconnecting" | "disconnected";

export interface ClusterMetricsState {
  snapshot:    MetricsSnapshot | null;
  status:      WSStatus;
  lastTick:    number | null;                      // epoch ms of last message
  cpuHistory:  Record<string, CpuHistoryPoint[]>;  // node_id → rolling history
}

/**
 * Maintains a persistent WebSocket connection to the gateway's /ws/metrics
 * endpoint. Auto-reconnects with exponential back-off on any close/error.
 */
export function useClusterMetrics(gatewayUrl: string): ClusterMetricsState {
  const [snapshot,   setSnapshot]   = useState<MetricsSnapshot | null>(null);
  const [status,     setStatus]     = useState<WSStatus>("connecting");
  const [lastTick,   setLastTick]   = useState<number | null>(null);
  const [cpuHistory, setCpuHistory] = useState<Record<string, CpuHistoryPoint[]>>({});

  const wsRef      = useRef<WebSocket | null>(null);
  const retryDelay = useRef(BASE_RECONNECT_MS);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmounted  = useRef(false);

  const connect = useCallback(() => {
    if (unmounted.current) return;

    // Build the WS URL from the HTTP API base URL
    const wsUrl = gatewayUrl
      .replace(/^http/, "ws")
      .replace(/\/$/, "") + "/ws/metrics";

    setStatus("connecting");

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmounted.current) { ws.close(); return; }
      retryDelay.current = BASE_RECONNECT_MS;   // reset backoff
      setStatus("connected");
    };

    ws.onmessage = (evt) => {
      if (unmounted.current) return;
      try {
        const data: MetricsSnapshot = JSON.parse(evt.data);
        const now = Date.now();
        setSnapshot(data);
        setLastTick(now);

        // Update CPU history for every node in this snapshot
        setCpuHistory((prev) => {
          const next = { ...prev };
          for (const node of data.nodes) {
            const pts = next[node.node_id] ?? [];
            next[node.node_id] = [
              ...pts.slice(-(HISTORY_LIMIT - 1)),
              { t: now, v: node.cpu.percent },
            ];
          }
          return next;
        });
      } catch {
        // silently ignore malformed frames
      }
    };

    ws.onclose = () => {
      if (unmounted.current) return;
      setStatus("reconnecting");
      scheduleReconnect();
    };

    ws.onerror = () => {
      ws.close();   // triggers onclose → reconnect
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gatewayUrl]);

  const scheduleReconnect = useCallback(() => {
    if (unmounted.current) return;
    if (retryTimer.current) clearTimeout(retryTimer.current);
    retryTimer.current = setTimeout(() => {
      retryDelay.current = Math.min(retryDelay.current * 2, MAX_RECONNECT_MS);
      connect();
    }, retryDelay.current);
  }, [connect]);

  useEffect(() => {
    unmounted.current = false;
    connect();

    return () => {
      unmounted.current = true;
      if (retryTimer.current) clearTimeout(retryTimer.current);
      wsRef.current?.close();
      setStatus("disconnected");
    };
  }, [connect]);

  return { snapshot, status, lastTick, cpuHistory };
}
