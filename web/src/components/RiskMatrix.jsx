import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Card } from "./ui";

const OWASP_LABELS = {
  "owasp:llm01": "LLM01 Prompt Injection",
  "owasp:llm02": "LLM02 Insecure Output Handling",
  "owasp:llm03": "LLM03 Training Data Poisoning",
  "owasp:llm04": "LLM04 Model Denial of Service",
  "owasp:llm05": "LLM05 Supply Chain",
  "owasp:llm06": "LLM06 Sensitive Info Disclosure",
  "owasp:llm07": "LLM07 Insecure Plugin Design",
  "owasp:llm08": "LLM08 Excessive Agency",
  "owasp:llm09": "LLM09 Overreliance",
  "owasp:llm10": "LLM10 Model Theft",
};

function cellColor(rate) {
  if (rate <= 0.05) return "bg-nvidia/20 text-nvidia border-nvidia/30";
  if (rate <= 0.25) return "bg-warn/15 text-warn border-warn/30";
  if (rate <= 0.6) return "bg-danger/15 text-danger border-danger/30";
  return "bg-danger/30 text-danger border-danger/50";
}

export default function RiskMatrix({ runId }) {
  const { data = [], isLoading } = useQuery({
    queryKey: ["riskMatrix", runId],
    queryFn: () => api.riskMatrix(runId),
  });

  if (isLoading) return <Card>Computing risk matrix…</Card>;
  if (data.length === 0)
    return <Card>No framework-tagged results to map for this run.</Card>;

  return (
    <div>
      <p className="text-sm text-ink-muted mb-4">
        Failure rate per OWASP LLM Top 10 category, aggregated from the framework
        tags each probe carries. Darker red = higher attack success.
      </p>
      <div className="grid grid-cols-2 gap-3">
        {data.map((row) => {
          const label = OWASP_LABELS[row.category] || row.category;
          return (
            <div
              key={row.category}
              className={`rounded-card border p-4 ${cellColor(row.failure_rate)}`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{label}</span>
                <span className="font-mono text-lg">
                  {Math.round(row.failure_rate * 100)}%
                </span>
              </div>
              <div className="text-xs opacity-80 mt-1 font-mono">
                {row.failed}/{row.total} failed · {row.probe_count} probes
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
