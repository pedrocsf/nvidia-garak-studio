import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Page, Card, StatusBadge, Empty, LinkButton } from "../components/ui";

export default function Runs() {
  const { data: runs = [], isLoading } = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.runs(),
    refetchInterval: 4000,
  });

  return (
    <Page
      title="Runs"
      subtitle="Scan execution history"
      actions={<LinkButton to="/scan" primary>New scan</LinkButton>}
    >
      {isLoading ? (
        <Empty>Loading…</Empty>
      ) : runs.length === 0 ? (
        <Empty>No runs yet.</Empty>
      ) : (
        <Card className="!p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-ink-muted text-xs border-b border-line">
                <th className="px-4 py-3 font-medium">Label</th>
                <th className="px-4 py-3 font-medium">Target</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Score</th>
                <th className="px-4 py-3 font-medium">Attempts</th>
                <th className="px-4 py-3 font-medium">Hits</th>
                <th className="px-4 py-3 font-medium">Started</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-b border-line/40 hover:bg-bg-elevated">
                  <td className="px-4 py-3">
                    <Link
                      to={r.status === "running" ? `/runs/${r.id}/live` : `/runs/${r.id}`}
                      className="hover:text-nvidia"
                    >
                      {r.label || r.id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-ink-muted">
                    {r.generator_type}:{r.target_model || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="px-4 py-3 font-mono">{r.attack_surface_score ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-ink-muted">{r.total_attempts}</td>
                  <td className="px-4 py-3 font-mono text-danger">{r.total_hits}</td>
                  <td className="px-4 py-3 text-xs text-ink-muted">
                    {r.started_at ? new Date(r.started_at).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </Page>
  );
}
