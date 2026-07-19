import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Page, Card, Stat, StatusBadge, Empty } from "../components/ui";

const STATES = [
  { value: "", label: "All" },
  { value: "new", label: "New" },
  { value: "confirmed", label: "Confirmed" },
  { value: "false_positive", label: "False positive" },
  { value: "accepted_risk", label: "Accepted risk" },
];

export default function Triage() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("");

  const { data: stats = {} } = useQuery({
    queryKey: ["triageStats"],
    queryFn: api.triageStats,
  });
  const { data: queue = [], isLoading } = useQuery({
    queryKey: ["triageQueue", status],
    queryFn: () => api.triageQueue(status ? { status } : {}),
  });

  async function setTriage(hitId, value) {
    await api.updateTriage(hitId, { triage_status: value });
    qc.invalidateQueries({ queryKey: ["triageQueue"] });
    qc.invalidateQueries({ queryKey: ["triageStats"] });
  }

  return (
    <Page
      title="Triage"
      subtitle="Review and classify hits like an issue tracker"
    >
      <div className="grid grid-cols-4 gap-4 mb-6">
        <Stat label="New" value={stats.new || 0} />
        <Stat label="Confirmed" value={stats.confirmed || 0} tone="bad" />
        <Stat label="False positive" value={stats.false_positive || 0} />
        <Stat label="Accepted risk" value={stats.accepted_risk || 0} tone="warn" />
      </div>

      <div className="flex gap-1 mb-4">
        {STATES.map((s) => (
          <button
            key={s.value}
            onClick={() => setStatus(s.value)}
            className={`text-xs px-3 py-1.5 rounded-md ${
              status === s.value
                ? "bg-bg-elevated text-ink"
                : "text-ink-muted hover:text-ink"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <Empty>Loading queue…</Empty>
      ) : queue.length === 0 ? (
        <Empty>Nothing to triage in this state.</Empty>
      ) : (
        <div className="space-y-2">
          {queue.map((h) => (
            <Card key={h.id}>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-xs text-nvidia">{h.probe}</span>
                    <span className="tag">{h.detector}</span>
                    <Link
                      to={`/runs/${h.run_id}`}
                      className="text-[11px] text-ink-muted hover:text-nvidia"
                    >
                      view run
                    </Link>
                  </div>
                  <div className="text-xs text-ink-muted font-mono line-clamp-2">
                    {h.prompt}
                  </div>
                  {h.triage_note && (
                    <div className="text-xs text-warn mt-1">note: {h.triage_note}</div>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2">
                  <StatusBadge status={h.triage_status} />
                  <div className="flex gap-1">
                    {STATES.slice(1).map((s) => (
                      <button
                        key={s.value}
                        onClick={() => setTriage(h.id, s.value)}
                        className={`text-[10px] px-2 py-1 rounded border ${
                          h.triage_status === s.value
                            ? "border-nvidia text-nvidia"
                            : "border-line text-ink-muted hover:text-ink"
                        }`}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </Page>
  );
}
