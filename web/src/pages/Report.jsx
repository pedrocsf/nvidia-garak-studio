import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileJson, History, ShieldAlert } from "lucide-react";
import { api } from "../lib/api";
import { Page, Card, Stat, ScoreTone, Meter, StatusBadge } from "../components/ui";
import RiskMatrix from "../components/RiskMatrix";
import HitBrowser from "../components/HitBrowser";

export default function Report() {
  const { runId } = useParams();
  const [tab, setTab] = useState("overview");

  const { data: run } = useQuery({ queryKey: ["run", runId], queryFn: () => api.run(runId) });
  const { data: results = [] } = useQuery({
    queryKey: ["results", runId],
    queryFn: () => api.runResults(runId),
  });

  return (
    <Page
      title={run?.label || "Report"}
      subtitle={
        run ? (
          <span className="font-mono">
            {run.generator_type}:{run.target_model} · {run.total_attempts} attempts
          </span>
        ) : (
          runId
        )
      }
      actions={
        <div className="flex gap-2">
          <Link className="btn-ghost" to={`/runs/${runId}/monitor`}>
            <History size={15} /> History
          </Link>
          <a className="btn-ghost" href={`/api/reports/${runId}/download/jsonl`}>
            <FileJson size={15} /> JSONL
          </a>
          <a className="btn-ghost" href={`/api/reports/${runId}/export/sarif`} target="_blank" rel="noreferrer">
            <Download size={15} /> SARIF
          </a>
        </div>
      }
    >
      {run && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <Stat
            label="Attack surface score"
            value={run.attack_surface_score ?? "—"}
            tone={ScoreTone(run.attack_surface_score)}
            sub="higher = more robust"
          />
          <Stat label="Attempts" value={run.total_attempts} />
          <Stat label="Hits (failures)" value={run.total_hits} tone="bad" />
          <div className="card p-4">
            <div className="label">Status</div>
            <StatusBadge status={run.status} />
            {run.error && <div className="text-xs text-danger mt-2">{run.error}</div>}
          </div>
        </div>
      )}

      <div className="flex gap-1 mb-4 border-b border-line">
        {["overview", "risk", "hits"].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm capitalize border-b-2 -mb-px ${
              tab === t
                ? "border-nvidia text-ink"
                : "border-transparent text-ink-muted hover:text-ink"
            }`}
          >
            {t === "risk" ? "Risk matrix" : t}
          </button>
        ))}
      </div>

      {tab === "overview" && <ResultsTable results={results} />}
      {tab === "risk" && <RiskMatrix runId={runId} />}
      {tab === "hits" && <HitBrowser runId={runId} />}
    </Page>
  );
}

function ResultsTable({ results }) {
  if (results.length === 0)
    return <Card>No per-probe results indexed for this run.</Card>;

  return (
    <Card className="!p-0 overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-ink-muted text-xs border-b border-line">
            <th className="px-4 py-3 font-medium">Probe</th>
            <th className="px-4 py-3 font-medium">Detector</th>
            <th className="px-4 py-3 font-medium w-48">Pass rate</th>
            <th className="px-4 py-3 font-medium">Failed / total</th>
            <th className="px-4 py-3 font-medium">95% CI</th>
            <th className="px-4 py-3 font-medium">Frameworks</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => {
            const rate = Math.round(r.pass_rate * 100);
            const tone = rate >= 90 ? "nvidia" : rate >= 70 ? "warn" : "danger";
            return (
              <tr key={i} className="border-b border-line/40 hover:bg-bg-elevated">
                <td className="px-4 py-3 font-mono text-xs">{r.probe}</td>
                <td className="px-4 py-3 font-mono text-xs text-ink-muted">{r.detector}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Meter value={rate} tone={tone} />
                    <span className="font-mono text-xs w-9">{rate}%</span>
                  </div>
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  <span className="text-danger">{r.failed}</span> / {r.total}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-ink-muted">
                  {r.ci_low != null && r.ci_high != null
                    ? `${r.ci_low.toFixed(2)}–${r.ci_high.toFixed(2)}`
                    : "—"}
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {(r.tags || [])
                      .filter((t) => /owasp|avid|mitre/i.test(t))
                      .slice(0, 3)
                      .map((t) => (
                        <span key={t} className="tag">
                          {t}
                        </span>
                      ))}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
