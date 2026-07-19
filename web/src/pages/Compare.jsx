import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { api } from "../lib/api";
import { Page, Card, Empty, ScoreTone } from "../components/ui";

function RunSelect({ label, value, onChange, runs }) {
  return (
    <div className="flex-1">
      <span className="label">{label}</span>
      <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Select a run…</option>
        {runs.map((r) => (
          <option key={r.id} value={r.id}>
            {(r.label || r.id.slice(0, 8)) +
              ` · ${r.generator_type}:${r.target_model || "?"} · score ${
                r.attack_surface_score ?? "—"
              }`}
          </option>
        ))}
      </select>
    </div>
  );
}

export default function Compare() {
  const [a, setA] = useState("");
  const [b, setB] = useState("");

  const { data: runs = [] } = useQuery({
    queryKey: ["runs", "completed"],
    queryFn: () => api.runs("completed"),
  });

  const { data: diff, isLoading } = useQuery({
    queryKey: ["compare", a, b],
    queryFn: () => api.compare(a, b),
    enabled: Boolean(a && b),
  });

  const regressed = diff?.diffs.filter((d) => d.direction === "regressed") || [];
  const improved = diff?.diffs.filter((d) => d.direction === "improved") || [];

  return (
    <Page
      title="Compare runs"
      subtitle="Diff two executions to spot regressions and improvements by probe"
    >
      <Card className="mb-6">
        <div className="flex items-end gap-4">
          <RunSelect label="Baseline (A)" value={a} onChange={setA} runs={runs} />
          <ArrowRight className="mb-2.5 text-ink-muted" size={20} />
          <RunSelect label="Comparison (B)" value={b} onChange={setB} runs={runs} />
        </div>
      </Card>

      {!a || !b ? (
        <Empty>Select two completed runs to compare.</Empty>
      ) : isLoading ? (
        <Empty>Computing diff…</Empty>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <ScoreCard title={diff.run_a.label || "A"} score={diff.run_a.score} />
            <div className="card p-4 flex flex-col items-center justify-center">
              <span className="label">Score delta</span>
              <ScoreDelta a={diff.run_a.score} b={diff.run_b.score} />
            </div>
            <ScoreCard title={diff.run_b.label || "B"} score={diff.run_b.score} />
          </div>

          <div className="grid grid-cols-2 gap-4 mb-6">
            <Card>
              <h3 className="text-sm font-semibold text-danger mb-2 flex items-center gap-2">
                <TrendingDown size={15} /> Regressions ({regressed.length})
              </h3>
              <p className="text-xs text-ink-muted">
                Probes where B performs worse than A.
              </p>
            </Card>
            <Card>
              <h3 className="text-sm font-semibold text-nvidia mb-2 flex items-center gap-2">
                <TrendingUp size={15} /> Improvements ({improved.length})
              </h3>
              <p className="text-xs text-ink-muted">
                Probes where B performs better than A.
              </p>
            </Card>
          </div>

          <Card className="!p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-ink-muted text-xs border-b border-line">
                  <th className="px-4 py-3 font-medium">Probe / detector</th>
                  <th className="px-4 py-3 font-medium">A pass rate</th>
                  <th className="px-4 py-3 font-medium">B pass rate</th>
                  <th className="px-4 py-3 font-medium">Δ</th>
                  <th className="px-4 py-3 font-medium">Significant?</th>
                </tr>
              </thead>
              <tbody>
                {diff.diffs.map((d, i) => (
                  <tr
                    key={i}
                    className={`border-b border-line/40 hover:bg-bg-elevated ${
                      d.direction === "regressed"
                        ? "bg-danger/5"
                        : d.direction === "improved"
                        ? "bg-nvidia/5"
                        : ""
                    }`}
                  >
                    <td className="px-4 py-3 font-mono text-xs">
                      {d.probe}
                      <span className="text-ink-muted"> / {d.detector}</span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">
                      {d.pass_rate_a != null ? `${Math.round(d.pass_rate_a * 100)}%` : "—"}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">
                      {d.pass_rate_b != null ? `${Math.round(d.pass_rate_b * 100)}%` : "—"}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">
                      <DirectionCell direction={d.direction} delta={d.delta} />
                    </td>
                    <td className="px-4 py-3">
                      {d.significant ? (
                        <span className="tag !text-nvidia !border-nvidia/40">yes</span>
                      ) : (
                        <span className="tag">noise</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </Page>
  );
}

function ScoreCard({ title, score }) {
  const tone = ScoreTone(score);
  const color =
    tone === "good" ? "text-nvidia" : tone === "warn" ? "text-warn" : "text-danger";
  return (
    <div className="card p-4 text-center">
      <div className="label truncate">{title}</div>
      <div className={`text-3xl font-mono font-semibold ${color}`}>{score ?? "—"}</div>
    </div>
  );
}

function ScoreDelta({ a, b }) {
  if (a == null || b == null) return <span className="text-ink-muted">—</span>;
  const d = +(b - a).toFixed(1);
  const cls = d > 0 ? "text-nvidia" : d < 0 ? "text-danger" : "text-ink-muted";
  const Icon = d > 0 ? TrendingUp : d < 0 ? TrendingDown : Minus;
  return (
    <span className={`text-2xl font-mono font-semibold flex items-center gap-1 ${cls}`}>
      <Icon size={20} /> {d > 0 ? "+" : ""}
      {d}
    </span>
  );
}

function DirectionCell({ direction, delta }) {
  if (delta == null) return <span className="text-ink-muted">—</span>;
  const cls =
    direction === "improved"
      ? "text-nvidia"
      : direction === "regressed"
      ? "text-danger"
      : "text-ink-muted";
  return (
    <span className={cls}>
      {delta > 0 ? "+" : ""}
      {Math.round(delta * 100)}%
    </span>
  );
}
