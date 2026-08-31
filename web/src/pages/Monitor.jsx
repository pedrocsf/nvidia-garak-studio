import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Activity, XCircle, FileBarChart } from "lucide-react";
import { api } from "../lib/api";
import { useRunSocket } from "../lib/useRunSocket";
import { Page, Card, StatusBadge, Meter } from "../components/ui";
import RunTimeline from "../components/RunTimeline";

const LIVE_STATUSES = ["queued", "running", "parsing"];

export default function Monitor() {
  const { runId } = useParams();

  const { data: run } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.run(runId),
    refetchInterval: (q) =>
      LIVE_STATUSES.includes(q.state.data?.status) ? 3000 : false,
  });

  const { status, probe, percent, connected, timelineEvents } = useRunSocket(runId, {
    enabled: LIVE_STATUSES.includes(run?.status),
  });

  const effectiveStatus = status || run?.status;
  const live = LIVE_STATUSES.includes(effectiveStatus);

  const liveCounts = useMemo(() => {
    let attempts = 0;
    let hits = 0;
    for (const e of timelineEvents) {
      if (e.kind !== "attempt") continue;
      attempts += 1;
      if (e.outcome === "hit") hits += 1;
    }
    return { attempts, hits };
  }, [timelineEvents]);

  const attempts = live ? liveCounts.attempts : run?.total_attempts ?? 0;
  const hits = live ? liveCounts.hits : run?.total_hits ?? 0;
  const hitRate = attempts ? (hits / attempts) * 100 : 0;

  async function cancel() {
    try {
      await api.cancelRun(runId);
    } catch (e) {
      alert(e.message);
    }
  }

  return (
    <Page
      title="Run Monitor"
      subtitle={run?.label || runId}
      actions={
        <div className="flex items-center gap-2">
          <Link to={`/runs/${runId}`} className="btn-ghost">
            <FileBarChart size={16} /> Report
          </Link>
          {live && (
            <button className="btn-ghost text-danger" onClick={cancel}>
              <XCircle size={16} /> Cancel
            </button>
          )}
        </div>
      }
    >
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-5">
        <Card>
          <div className="flex items-center justify-between mb-2">
            <span className="label !mb-0">Status</span>
            <StatusBadge status={effectiveStatus} />
          </div>
          <div className="text-[11px] text-ink-muted font-mono">
            {live ? (connected ? "● streaming" : "○ connecting…") : "history"}
          </div>
        </Card>

        <Card>
          <span className="label">Current probe</span>
          <div className="font-mono text-xs truncate" title={probe || ""}>
            {probe || "—"}
          </div>
        </Card>

        <Card>
          <span className="label">Attempts</span>
          <div className="text-xl font-semibold font-mono">
            {attempts.toLocaleString()}
          </div>
        </Card>

        <Card>
          <span className="label">Hits</span>
          <div
            className={`text-xl font-semibold font-mono ${
              hits ? "text-danger" : "text-nvidia"
            }`}
          >
            {hits.toLocaleString()}
            {attempts > 0 && (
              <span className="text-[11px] text-ink-muted ml-2 font-normal">
                {hitRate.toFixed(1)}%
              </span>
            )}
          </div>
        </Card>

        <Card>
          <span className="label">Progress</span>
          <div className="flex items-center gap-3">
            <Meter value={percent ?? (live ? 5 : 100)} />
            <span className="font-mono text-xs w-10 text-right">
              {percent != null ? `${percent}%` : live ? "—" : "done"}
            </span>
          </div>
        </Card>
      </div>

      <div className="flex items-center gap-2 mb-3 text-xs text-ink-muted">
        <Activity size={14} />
        <span>
          Every operation and verdict garak recorded, parsed from the run's report
          on disk — searchable, sortable, and rebuildable without this database.
        </span>
      </div>

      <RunTimeline runId={runId} live={live} />
    </Page>
  );
}
