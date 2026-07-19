import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, RefreshCw, ExternalLink } from "lucide-react";
import { api } from "../lib/api";
import { Page, Card, Empty } from "../components/ui";

const CATEGORIES = ["probes", "detectors", "generators", "harnesses", "buffs"];

export default function Plugins() {
  const qc = useQueryClient();
  const [category, setCategory] = useState("probes");
  const [q, setQ] = useState("");

  const { data: summary } = useQuery({
    queryKey: ["pluginSummary"],
    queryFn: api.pluginSummary,
    retry: false,
  });

  const { data = [], isLoading, error } = useQuery({
    queryKey: ["plugins", category],
    queryFn: () => api.plugins(category, true),
    retry: false,
  });

  const filtered = useMemo(() => {
    const needle = q.toLowerCase();
    return data.filter(
      (p) =>
        !needle ||
        p.name.toLowerCase().includes(needle) ||
        (p.description || "").toLowerCase().includes(needle) ||
        (p.tags || []).some((t) => t.toLowerCase().includes(needle))
    );
  }, [data, q]);

  async function refresh() {
    await api.refreshPlugins();
    qc.invalidateQueries({ queryKey: ["plugins"] });
    qc.invalidateQueries({ queryKey: ["pluginSummary"] });
  }

  return (
    <Page
      title="Plugins"
      subtitle={
        summary
          ? `Discovered dynamically from garak ${summary.version} — no hardcoded lists`
          : "Introspecting the installed garak…"
      }
      actions={
        <button className="btn-ghost" onClick={refresh}>
          <RefreshCw size={15} /> Rescan
        </button>
      }
    >
      <div className="flex gap-1 mb-4">
        {CATEGORIES.map((c) => (
          <button
            key={c}
            onClick={() => setCategory(c)}
            className={`text-sm px-3 py-1.5 rounded-md capitalize ${
              category === c ? "bg-bg-elevated text-ink" : "text-ink-muted hover:text-ink"
            }`}
          >
            {c}
            {summary && (
              <span className="ml-1.5 text-[11px] font-mono text-ink-muted">
                {summary.counts[c]}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="relative mb-4">
        <Search size={15} className="absolute left-3 top-2.5 text-ink-muted" />
        <input
          className="input pl-9"
          placeholder={`Search ${category}…`}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      {error ? (
        <Empty>
          Could not load {category}: {error.message}
        </Empty>
      ) : isLoading ? (
        <Empty>Loading {category}…</Empty>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          {filtered.map((p) => (
            <Card key={p.name}>
              <div className="flex items-start justify-between gap-2">
                <span className="font-mono text-sm text-nvidia break-all">
                  {p.name.replace(`${category}.`, "")}
                </span>
                {!p.active && <span className="tag">inactive</span>}
              </div>
              {p.goal && <div className="text-xs text-ink mt-1.5">{p.goal}</div>}
              {p.description && (
                <div className="text-xs text-ink-muted mt-1 line-clamp-2">
                  {p.description}
                </div>
              )}
              {p.primary_detector && (
                <div className="text-[11px] text-ink-muted mt-2 font-mono">
                  detector: {p.primary_detector}
                </div>
              )}
              <div className="flex flex-wrap gap-1 mt-2">
                {(p.tags || []).map((t) => (
                  <span key={t} className="tag">
                    {t}
                  </span>
                ))}
              </div>
              {p.doc_url && (
                <a
                  href={p.doc_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[11px] text-nvidia hover:underline mt-2 inline-flex items-center gap-1"
                >
                  <ExternalLink size={11} /> docs
                </a>
              )}
            </Card>
          ))}
          {filtered.length === 0 && <Empty>No matches.</Empty>}
        </div>
      )}
    </Page>
  );
}
