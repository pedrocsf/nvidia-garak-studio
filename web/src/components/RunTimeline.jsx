import { useEffect, useMemo, useState } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  ChevronsUpDown,
  ArrowDown,
  ArrowUp,
  Search,
  RefreshCw,
  Download,
  Database,
  FileText,
  X,
} from "lucide-react";
import { api } from "../lib/api";

const PAGE_SIZE = 100;

const KIND_META = {
  run_start: { label: "run start", tone: "text-ink" },
  config: { label: "config", tone: "text-ink-muted" },
  probe_start: { label: "probe", tone: "text-nvidia" },
  attempt: { label: "attempt", tone: "text-ink" },
  eval: { label: "eval", tone: "text-warn" },
  payload: { label: "payload", tone: "text-ink-muted" },
  tree: { label: "tree node", tone: "text-ink-muted" },
  run_end: { label: "run end", tone: "text-ink" },
  console: { label: "console", tone: "text-ink-muted" },
  error: { label: "error", tone: "text-danger" },
};

const OUTCOME_STYLE = {
  hit: "bg-danger/15 text-danger border-danger/30",
  pass: "bg-nvidia/15 text-nvidia border-nvidia/30",
  info: "bg-bg-elevated text-ink-muted border-line",
  error: "bg-danger/15 text-danger border-danger/30",
};

const COLUMNS = [
  { key: "seq", label: "#", width: "w-16", sortable: true },
  { key: "kind", label: "Kind", width: "w-28", sortable: true },
  { key: "probe", label: "Probe", width: "w-52", sortable: true },
  { key: "title", label: "Event", width: "", sortable: true },
  { key: "outcome", label: "Outcome", width: "w-24", sortable: true },
  { key: "score", label: "Score", width: "w-20", sortable: true },
];

function OutcomeBadge({ outcome }) {
  if (!outcome) return null;
  return (
    <span
      className={`text-[10px] px-1.5 py-0.5 rounded border font-medium uppercase tracking-wide ${
        OUTCOME_STYLE[outcome] || OUTCOME_STYLE.info
      }`}
    >
      {outcome}
    </span>
  );
}

function SortIcon({ active, order }) {
  if (!active) return <ChevronsUpDown size={12} className="opacity-30" />;
  return order === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />;
}

function Facet({ title, counts, selected, onToggle }) {
  const entries = Object.entries(counts || {}).filter(([, n]) => n > 0);
  if (!entries.length) return null;
  entries.sort((a, b) => b[1] - a[1]);
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <span className="text-[10px] uppercase tracking-wide text-ink-muted mr-1">
        {title}
      </span>
      {entries.map(([value, n]) => {
        const active = selected.includes(value);
        return (
          <button
            key={value}
            onClick={() => onToggle(value)}
            className={`text-[11px] px-2 py-0.5 rounded border transition-colors ${
              active
                ? "bg-nvidia/15 text-nvidia border-nvidia/40"
                : "bg-bg-base text-ink-muted border-line hover:text-ink"
            }`}
          >
            {KIND_META[value]?.label || value}
            <span className="ml-1.5 opacity-60 font-mono">{n}</span>
          </button>
        );
      })}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-ink-muted mb-1">
        {label}
      </div>
      {children}
    </div>
  );
}

function Pre({ children, className = "" }) {
  return (
    <pre
      className={`font-mono text-xs whitespace-pre-wrap break-words bg-bg-base
                  border border-line rounded p-3 max-h-80 overflow-y-auto ${className}`}
    >
      {children}
    </pre>
  );
}

function DetectorScores({ scores, firing = [], threshold }) {
  const entries = Object.entries(scores || {});
  if (!entries.length) return <span className="text-ink-muted text-xs">—</span>;
  return (
    <div className="space-y-1">
      {entries.map(([name, values]) => {
        const best = Math.max(...values);
        const fired = firing.includes(name);
        return (
          <div key={name} className="flex items-center gap-2 text-xs">
            <span className={`font-mono ${fired ? "text-danger" : "text-ink-muted"}`}>
              {name}
            </span>
            <div className="flex-1 h-1 bg-bg-elevated rounded overflow-hidden min-w-[60px]">
              <div
                className={fired ? "h-full bg-danger" : "h-full bg-nvidia"}
                style={{ width: `${Math.min(100, best * 100)}%` }}
              />
            </div>
            <span className="font-mono w-10 text-right">{best.toFixed(2)}</span>
            {values.length > 1 && (
              <span className="text-ink-muted text-[10px]">×{values.length}</span>
            )}
          </div>
        );
      })}
      {threshold != null && (
        <div className="text-[10px] text-ink-muted pt-0.5">
          fails at ≥ {threshold}
        </div>
      )}
    </div>
  );
}

function EventDetail({ runId, seq, stream }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["timelineEvent", runId, stream, seq],
    queryFn: () => api.timelineEvent(runId, seq, { stream }),
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading)
    return <div className="px-6 py-4 text-xs text-ink-muted">Loading detail…</div>;
  if (error)
    return <div className="px-6 py-4 text-xs text-danger">{error.message}</div>;

  const d = data?.detail || {};
  const turns = d.turns || [];
  const outputs = d.outputs || [];

  return (
    <div className="px-6 py-4 bg-bg-base/60 border-t border-line space-y-4">
      {(d.goal || d.probe) && (
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs">
          {d.probe && (
            <div>
              <span className="text-ink-muted">probe </span>
              <span className="font-mono">{d.probe}</span>
            </div>
          )}
          {d.goal && (
            <div>
              <span className="text-ink-muted">goal </span>
              <span>{d.goal}</span>
            </div>
          )}
          {data.attempt_uuid && (
            <div>
              <span className="text-ink-muted">attempt </span>
              <span className="font-mono">{data.attempt_uuid}</span>
            </div>
          )}
        </div>
      )}

      {d.prompt != null && (
        <Field label="Prompt sent">
          <Pre>{d.prompt || "(empty)"}</Pre>
        </Field>
      )}

      {outputs.length > 0 && (
        <Field label={outputs.length > 1 ? `Outputs (${outputs.length})` : "Output"}>
          <div className="space-y-2">
            {outputs.map((o, i) => (
              <Pre key={i}>{o || "(empty)"}</Pre>
            ))}
          </div>
        </Field>
      )}

      {d.detector_scores && (
        <Field label="Detector verdicts">
          <DetectorScores
            scores={d.detector_scores}
            firing={d.firing_detectors}
            threshold={d.hit_threshold}
          />
        </Field>
      )}

      {turns.length > 1 && (
        <Field label={`Conversation (${turns.length} turns)`}>
          <div className="space-y-1.5">
            {turns.map((t, i) => (
              <div
                key={i}
                className={`rounded p-2 border ${
                  t.role === "assistant"
                    ? "bg-bg-elevated border-line"
                    : "bg-bg-base border-line"
                }`}
              >
                <div className="text-[10px] uppercase text-ink-muted mb-1">
                  {t.role}
                </div>
                <div className="font-mono text-xs whitespace-pre-wrap break-words">
                  {t.text}
                </div>
              </div>
            ))}
          </div>
        </Field>
      )}

      {data.kind === "eval" && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          {[
            ["passed", d.passed],
            ["failed", d.failed],
            ["total", d.total],
            ["pass rate", d.pass_rate != null ? `${(d.pass_rate * 100).toFixed(1)}%` : "—"],
            ["conf. lower", d.confidence_lower],
            ["conf. upper", d.confidence_upper],
            ["nones", d.nones],
            ["processed", d.total_processed],
          ].map(([k, v]) =>
            v == null ? null : (
              <div key={k} className="card p-2.5">
                <div className="text-[10px] uppercase text-ink-muted">{k}</div>
                <div className="font-mono text-sm">{String(v)}</div>
              </div>
            )
          )}
        </div>
      )}

      {d.line && (
        <Field label="Console line">
          <Pre>{d.line}</Pre>
        </Field>
      )}

      {d.config && (
        <Field label="Resolved configuration">
          <Pre>{JSON.stringify(d.config, null, 2)}</Pre>
        </Field>
      )}

      {d.notes && Object.keys(d.notes).length > 0 && (
        <Field label="Probe notes">
          <Pre>{JSON.stringify(d.notes, null, 2)}</Pre>
        </Field>
      )}

      <details className="text-xs">
        <summary className="cursor-pointer text-ink-muted hover:text-ink">
          Raw event
        </summary>
        <Pre className="mt-2">{JSON.stringify(data, null, 2)}</Pre>
      </details>
    </div>
  );
}

export default function RunTimeline({ runId, live = false, className = "" }) {
  const qc = useQueryClient();
  const [stream, setStream] = useState("report");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [kinds, setKinds] = useState([]);
  const [outcomes, setOutcomes] = useState([]);
  const [probe, setProbe] = useState("");
  const [sort, setSort] = useState("seq");
  const [order, setOrder] = useState("asc");
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState(null);
  const [rebuilding, setRebuilding] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => {
      setQ(search);
      setPage(0);
    }, 250);
    return () => clearTimeout(t);
  }, [search]);

  const params = useMemo(
    () => ({
      q,
      stream,
      kind: kinds.join(","),
      outcome: outcomes.join(","),
      probe,
      sort,
      order,
      offset: page * PAGE_SIZE,
      limit: PAGE_SIZE,
    }),
    [q, stream, kinds, outcomes, probe, sort, order, page]
  );

  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ["timeline", runId, params],
    queryFn: () => api.timeline(runId, params),
    placeholderData: keepPreviousData,
    refetchInterval: live ? 2000 : false,
  });

  const { data: meta } = useQuery({
    queryKey: ["timelineMeta", runId],
    queryFn: () => api.timelineMeta(runId),
  });

  const events = data?.events || [];
  const total = data?.total || 0;
  const pages = Math.ceil(total / PAGE_SIZE);
  const facets = data?.facets || {};

  function toggleSort(key) {
    if (sort === key) {
      setOrder((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setSort(key);
      setOrder(key === "score" ? "desc" : "asc");
    }
    setPage(0);
  }

  function toggleIn(list, setList, value) {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
    setPage(0);
  }

  function clearFilters() {
    setSearch("");
    setKinds([]);
    setOutcomes([]);
    setProbe("");
    setPage(0);
  }

  async function rebuild() {
    setRebuilding(true);
    try {
      const res = await api.rebuildTimeline(runId);
      await qc.invalidateQueries({ queryKey: ["timeline", runId] });
      await qc.invalidateQueries({ queryKey: ["timelineMeta", runId] });
      alert(
        `Rebuilt from disk.\n\nreport: ${res.counts.report} events\nconsole: ${res.counts.console} lines`
      );
    } catch (e) {
      alert(e.message);
    } finally {
      setRebuilding(false);
    }
  }

  const hasFilters = q || kinds.length || outcomes.length || probe;

  return (
    <div className={`card !p-0 ${className}`}>
      <div className="px-4 py-3 border-b border-line space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex rounded-md border border-line overflow-hidden">
            {["report", "console"].map((s) => (
              <button
                key={s}
                onClick={() => {
                  setStream(s);
                  setPage(0);
                  setExpanded(null);
                  setKinds([]);
                  setOutcomes([]);
                }}
                className={`text-xs px-3 py-1.5 transition-colors ${
                  stream === s
                    ? "bg-bg-elevated text-ink"
                    : "text-ink-muted hover:text-ink"
                }`}
              >
                {s === "report" ? "Timeline" : "Console"}
              </button>
            ))}
          </div>

          <div className="relative flex-1 min-w-[220px]">
            <Search
              size={14}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted"
            />
            <input
              className="input !pl-8 !py-1.5"
              placeholder="Search prompts, outputs, probes, detectors…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {search && (
              <button
                onClick={() => setSearch("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-muted hover:text-ink"
              >
                <X size={13} />
              </button>
            )}
          </div>

          {hasFilters && (
            <button className="btn-ghost !py-1.5 !text-xs" onClick={clearFilters}>
              Clear
            </button>
          )}

          <button
            className="btn-ghost !py-1.5 !text-xs"
            onClick={rebuild}
            disabled={rebuilding}
            title="Re-read the garak report from disk and rebuild the search index"
          >
            <RefreshCw size={13} className={rebuilding ? "animate-spin" : ""} />
            Rebuild
          </button>

          <a
            className="btn-ghost !py-1.5 !text-xs"
            href={api.timelineExportUrl(runId)}
            title="Download the whole history as JSONL"
          >
            <Download size={13} />
            Export
          </a>
        </div>

        {stream === "report" && (
          <div className="space-y-2">
            <Facet
              title="kind"
              counts={facets.kind}
              selected={kinds}
              onToggle={(v) => toggleIn(kinds, setKinds, v)}
            />
            <Facet
              title="outcome"
              counts={facets.outcome}
              selected={outcomes}
              onToggle={(v) => toggleIn(outcomes, setOutcomes, v)}
            />
          </div>
        )}

        <div className="flex items-center justify-between text-[11px] text-ink-muted">
          <div className="flex items-center gap-3">
            <span className="font-mono">
              {total.toLocaleString()} event{total === 1 ? "" : "s"}
              {hasFilters ? " matched" : ""}
            </span>
            {probe && (
              <button
                onClick={() => {
                  setProbe("");
                  setPage(0);
                }}
                className="text-nvidia hover:underline font-mono"
              >
                probe: {probe} ✕
              </button>
            )}
            {isFetching && <span>updating…</span>}
          </div>
          <div className="flex items-center gap-1.5" title="Where this view is reading from">
            {data?.source === "index" ? (
              <>
                <Database size={11} /> index
              </>
            ) : (
              <>
                <FileText size={11} /> report file
              </>
            )}
            {meta?.report_path && (
              <span className="font-mono opacity-50 hidden lg:inline">
                · {meta.report_path.split("/").slice(-1)[0]}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 px-4 py-2 border-b border-line text-[10px] uppercase tracking-wide text-ink-muted">
        <span className="w-4" />
        {COLUMNS.map((c) => (
          <button
            key={c.key}
            onClick={() => c.sortable && toggleSort(c.key)}
            className={`flex items-center gap-1 ${c.width} ${
              c.key === "title" ? "flex-1 text-left" : ""
            } ${c.sortable ? "hover:text-ink" : "cursor-default"}`}
          >
            {c.label}
            {c.sortable && <SortIcon active={sort === c.key} order={order} />}
          </button>
        ))}
      </div>

      <div className="max-h-[60vh] overflow-y-auto">
        {isLoading ? (
          <div className="px-4 py-10 text-center text-sm text-ink-muted">
            Loading history…
          </div>
        ) : error ? (
          <div className="px-4 py-10 text-center text-sm text-danger">
            {error.message}
          </div>
        ) : !events.length ? (
          <div className="px-4 py-10 text-center text-sm text-ink-muted">
            {hasFilters
              ? "No events match these filters."
              : "No history recorded for this run yet."}
          </div>
        ) : (
          events.map((e) => {
            const open = expanded === e.seq;
            const kind = KIND_META[e.kind] || { label: e.kind, tone: "text-ink-muted" };
            return (
              <div key={`${e.seq}-${e.kind}`} className="border-b border-line/60">
                <button
                  onClick={() => setExpanded(open ? null : e.seq)}
                  className={`w-full flex items-center gap-3 px-4 py-2 text-left text-xs
                              hover:bg-bg-elevated/50 transition-colors ${
                                open ? "bg-bg-elevated/40" : ""
                              }`}
                >
                  <span className="w-4 text-ink-muted shrink-0">
                    {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                  </span>
                  <span className="w-16 font-mono text-ink-muted shrink-0">{e.seq}</span>
                  <span className={`w-28 shrink-0 ${kind.tone}`}>{kind.label}</span>
                  <span
                    className="w-52 shrink-0 font-mono text-ink-muted truncate"
                    title={e.probe}
                    onClick={(ev) => {
                      if (!e.probe) return;
                      ev.stopPropagation();
                      setProbe(e.probe);
                      setPage(0);
                    }}
                  >
                    {e.probe || "—"}
                  </span>
                  <span className="flex-1 truncate" title={e.title}>
                    {e.title}
                    {e.summary && (
                      <span className="text-ink-muted"> · {e.summary}</span>
                    )}
                  </span>
                  <span className="w-24 shrink-0">
                    <OutcomeBadge outcome={e.outcome} />
                  </span>
                  <span className="w-20 shrink-0 font-mono text-right">
                    {e.score != null ? e.score.toFixed(2) : "—"}
                  </span>
                </button>
                {open && <EventDetail runId={runId} seq={e.seq} stream={stream} />}
              </div>
            );
          })
        )}
      </div>

      {pages > 1 && (
        <div className="flex items-center justify-between px-4 py-2.5 border-t border-line text-xs">
          <span className="text-ink-muted font-mono">
            {(page * PAGE_SIZE + 1).toLocaleString()}–
            {Math.min((page + 1) * PAGE_SIZE, total).toLocaleString()} of{" "}
            {total.toLocaleString()}
          </span>
          <div className="flex items-center gap-1">
            <button
              className="btn-ghost !py-1 !px-2"
              disabled={page === 0}
              onClick={() => setPage(0)}
            >
              First
            </button>
            <button
              className="btn-ghost !py-1 !px-2"
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
            >
              Prev
            </button>
            <span className="px-2 font-mono text-ink-muted">
              {page + 1} / {pages}
            </span>
            <button
              className="btn-ghost !py-1 !px-2"
              disabled={page >= pages - 1}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
            <button
              className="btn-ghost !py-1 !px-2"
              disabled={page >= pages - 1}
              onClick={() => setPage(pages - 1)}
            >
              Last
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
