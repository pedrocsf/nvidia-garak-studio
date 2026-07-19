import { useEffect, useRef, useState } from "react";
import { runSocketUrl } from "./api";

export function useRunSocket(runId, { enabled = true } = {}) {
  const [logs, setLogs] = useState([]);
  const [status, setStatus] = useState(null);
  const [probe, setProbe] = useState(null);
  const [percent, setPercent] = useState(null);
  const [turns, setTurns] = useState([]);
  const [connected, setConnected] = useState(false);
  const [metrics, setMetrics] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!runId || !enabled) return undefined;
    let closed = false;
    let retry;

    function connect() {
      const ws = new WebSocket(runSocketUrl(runId));
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closed) retry = setTimeout(connect, 1500);
      };
      ws.onmessage = (ev) => {
        let msg;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        switch (msg.type) {
          case "log":
            setLogs((prev) => [...prev.slice(-2000), msg]);
            if (msg.percent != null) setPercent(msg.percent);
            break;
          case "probe":
            setProbe(msg.probe);
            break;
          case "turn":
            setTurns((prev) => [...prev, msg]);
            break;
          case "status":
            setStatus(msg.status);
            if (msg.metrics) setMetrics(msg.metrics);
            break;
          default:
            break;
        }
      };
    }

    connect();
    return () => {
      closed = true;
      clearTimeout(retry);
      wsRef.current?.close();
    };
  }, [runId, enabled]);

  return { logs, status, probe, percent, turns, connected, metrics };
}
