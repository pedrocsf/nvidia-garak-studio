import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { XCircle, Terminal, MessagesSquare } from "lucide-react";
import { api } from "../lib/api";
import { useRunSocket } from "../lib/useRunSocket";
import { Page, Card, StatusBadge, Meter } from "../components/ui";

export default function LiveRun() {
  const { runId } = useParams();
  const nav = useNavigate();
  const [levelFilter, setLevelFilter] = useState("all");
  const logEndRef = useRef(null);

  const { data: run } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.run(runId),
    refetchInterval: (q) =>
      ["completed", "failed", "cancelled"].includes(q.state.data?.status) ? false : 3000,
  });

  const { logs, status, probe, percent, connected, turns } = useRunSocket(runId);
  const effectiveStatus = status || run?.status;

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  useEffect(() => {
    if (["completed"].includes(effectiveStatus)) {
      const t = setTimeout(() => nav(`/runs/${runId}`), 1500);
      return () => clearTimeout(t);
    }
  }, [effectiveStatus, nav, runId]);

  async function cancel() {
    try {
      await api.cancelRun(runId);
    } catch (e) {
      alert(e.message);
    }
  }

  const visibleLogs = logs.filter((l) => {
    if (levelFilter === "all") return true;
    const line = (l.line || "").toLowerCase();
    if (levelFilter === "error") return /error|fail|traceback|exception/.test(line);
    return true;
  });

  const running = ["queued", "running", "parsing"].includes(effectiveStatus);

  return (
    <Page
      title="Live Run"
      subtitle={run?.label || runId}
      actions={
        running ? (
          <button className="btn-ghost text-danger" onClick={cancel}>
            <XCircle size={16} /> Cancel
          </button>
        ) : null
      }
    >
      <div className="grid grid-cols-3 gap-4 mb-5">
        <Card>
          <div className="flex items-center justify-between mb-2">
            <span className="label !mb-0">Status</span>
            <StatusBadge status={effectiveStatus} />
          </div>
          <div className="text-xs text-ink-muted font-mono">
            {connected ? "● stream connected" : "○ connecting…"}
          </div>
        </Card>
        <Card>
          <span className="label">Current probe</span>
          <div className="font-mono text-sm truncate">{probe || "—"}</div>
        </Card>
        <Card>
          <span className="label">Progress</span>
          <div className="flex items-center gap-3">
            <Meter value={percent ?? (running ? 5 : 100)} />
            <span className="font-mono text-xs w-10 text-right">
              {percent != null ? `${percent}%` : "—"}
            </span>
          </div>
        </Card>
      </div>

      {turns.length > 0 && (
        <Card className="mb-5">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <MessagesSquare size={15} /> Multi-turn conversation
          </h3>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {turns.map((t, i) => (
              <div
                key={i}
                className={`text-sm p-2 rounded ${
                  t.role === "assistant" ? "bg-bg-elevated" : "bg-bg-base border border-line"
                }`}
              >
                <span className="text-[10px] uppercase text-ink-muted">{t.role}</span>
                <div className="font-mono text-xs mt-1">{t.content}</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card className="!p-0">
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-line">
          <span className="text-sm font-semibold flex items-center gap-2">
            <Terminal size={15} /> Execution log
          </span>
          <div className="flex gap-1">
            {["all", "error"].map((lv) => (
              <button
                key={lv}
                onClick={() => setLevelFilter(lv)}
                className={`text-xs px-2 py-1 rounded ${
                  levelFilter === lv ? "bg-bg-elevated text-ink" : "text-ink-muted"
                }`}
              >
                {lv}
              </button>
            ))}
          </div>
        </div>
        <div className="p-4 font-mono text-xs leading-relaxed max-h-[45vh] overflow-y-auto">
          {visibleLogs.length === 0 ? (
            <div className="text-ink-muted">Waiting for output…</div>
          ) : (
            visibleLogs.map((l, i) => (
              <div
                key={i}
                className={
                  /error|fail|traceback|exception/i.test(l.line || "")
                    ? "text-danger"
                    : "text-ink-muted"
                }
              >
                {l.line}
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </Card>
    </Page>
  );
}
