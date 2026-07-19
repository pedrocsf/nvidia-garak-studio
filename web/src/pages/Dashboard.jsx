import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Page, Card, Stat, StatusBadge, Meter, ScoreTone, Empty } from "../components/ui";

export default function Dashboard() {
  const { data: runs = [] } = useQuery({ queryKey: ["runs"], queryFn: () => api.runs() });
  const { data: summary } = useQuery({
    queryKey: ["pluginSummary"],
    queryFn: api.pluginSummary,
    retry: false,
  });

  const completed = runs.filter((r) => r.status === "completed");
  const latest = completed[0];
  const monitored = {};
  for (const r of completed) {
    if (r.target_model && !monitored[r.target_model]) monitored[r.target_model] = r;
  }

  const totalPlugins = summary
    ? Object.values(summary.counts).reduce((a, b) => a + b, 0)
    : null;

  return (
    <Page
      title="Dashboard"
      subtitle="Overview of scan activity and target robustness"
    >
      <div className="grid grid-cols-4 gap-4 mb-6">
        <Stat label="Total runs" value={runs.length} />
        <Stat
          label="Latest score"
          value={latest?.attack_surface_score ?? "—"}
          tone={ScoreTone(latest?.attack_surface_score)}
          sub={latest?.target_model}
        />
        <Stat
          label="Open hits"
          value={completed.reduce((a, r) => a + (r.total_hits || 0), 0)}
          tone="bad"
        />
        <Stat
          label="Plugins discovered"
          value={totalPlugins ?? "—"}
          tone="good"
          sub={summary ? `garak ${summary.version}` : "garak unavailable"}
        />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2">
          <h2 className="text-sm font-semibold mb-3">Recent runs</h2>
          {runs.length === 0 ? (
            <Empty>
              No runs yet.{" "}
              <Link to="/scan" className="text-nvidia hover:underline">
                Start your first scan →
              </Link>
            </Empty>
          ) : (
            <Card className="!p-0 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-ink-muted text-xs border-b border-line">
                    <th className="px-4 py-2.5 font-medium">Label</th>
                    <th className="px-4 py-2.5 font-medium">Status</th>
                    <th className="px-4 py-2.5 font-medium">Score</th>
                    <th className="px-4 py-2.5 font-medium">Hits</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.slice(0, 8).map((r) => (
                    <tr key={r.id} className="border-b border-line/50 hover:bg-bg-elevated">
                      <td className="px-4 py-2.5">
                        <Link
                          to={r.status === "running" ? `/runs/${r.id}/live` : `/runs/${r.id}`}
                          className="hover:text-nvidia"
                        >
                          {r.label || r.id.slice(0, 8)}
                        </Link>
                      </td>
                      <td className="px-4 py-2.5">
                        <StatusBadge status={r.status} />
                      </td>
                      <td className="px-4 py-2.5 font-mono">
                        {r.attack_surface_score ?? "—"}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-danger">
                        {r.total_hits || 0}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>

        <div>
          <h2 className="text-sm font-semibold mb-3">Monitored targets</h2>
          {Object.keys(monitored).length === 0 ? (
            <Empty>No completed scans yet.</Empty>
          ) : (
            <div className="space-y-3">
              {Object.values(monitored).map((r) => (
                <Card key={r.id}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-mono truncate">{r.target_model}</span>
                    <span
                      className={`font-mono text-sm ${
                        ScoreTone(r.attack_surface_score) === "good"
                          ? "text-nvidia"
                          : ScoreTone(r.attack_surface_score) === "warn"
                          ? "text-warn"
                          : "text-danger"
                      }`}
                    >
                      {r.attack_surface_score ?? "—"}
                    </span>
                  </div>
                  <Meter
                    value={r.attack_surface_score ?? 0}
                    tone={
                      ScoreTone(r.attack_surface_score) === "good"
                        ? "nvidia"
                        : ScoreTone(r.attack_surface_score) === "warn"
                        ? "warn"
                        : "danger"
                    }
                  />
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </Page>
  );
}
