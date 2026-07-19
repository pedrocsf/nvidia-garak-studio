import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, MessagesSquare } from "lucide-react";
import { api } from "../lib/api";
import { Card, StatusBadge, Empty } from "./ui";

const TRIAGE_OPTIONS = [
  { value: "new", label: "New" },
  { value: "confirmed", label: "Confirmed" },
  { value: "false_positive", label: "False positive" },
  { value: "accepted_risk", label: "Accepted risk" },
];

export default function HitBrowser({ runId }) {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 25;

  const { data: hits = [], isLoading } = useQuery({
    queryKey: ["hits", runId, q, status, offset],
    queryFn: () =>
      api.hits(runId, {
        ...(q ? { q } : {}),
        ...(status ? { triage_status: status } : {}),
        offset,
        limit,
      }),
    keepPreviousData: true,
  });

  const { data: count } = useQuery({
    queryKey: ["hitCount", runId],
    queryFn: () => api.hitCount(runId),
  });

  async function triage(hitId, patch) {
    await api.updateTriage(hitId, patch);
    qc.invalidateQueries({ queryKey: ["hits", runId] });
    qc.invalidateQueries({ queryKey: ["triageStats"] });
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3 top-2.5 text-ink-muted" />
          <input
            className="input pl-9"
            placeholder="Search prompts & outputs…"
            value={q}
            onChange={(e) => {
              setOffset(0);
              setQ(e.target.value);
            }}
          />
        </div>
        <select
          className="input !w-48"
          value={status}
          onChange={(e) => {
            setOffset(0);
            setStatus(e.target.value);
          }}
        >
          <option value="">All triage states</option>
          {TRIAGE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <span className="text-xs text-ink-muted font-mono whitespace-nowrap">
          {count?.count ?? 0} total
        </span>
      </div>

      {isLoading ? (
        <Empty>Loading hits…</Empty>
      ) : hits.length === 0 ? (
        <Empty>No hits match.</Empty>
      ) : (
        <div className="space-y-3">
          {hits.map((h) => (
            <HitCard key={h.id} hit={h} onTriage={triage} />
          ))}
        </div>
      )}

      <div className="flex items-center justify-between mt-4">
        <button
          className="btn-ghost"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - limit))}
        >
          ← Prev
        </button>
        <span className="text-xs text-ink-muted font-mono">
          {offset + 1}–{offset + hits.length}
        </span>
        <button
          className="btn-ghost"
          disabled={hits.length < limit}
          onClick={() => setOffset(offset + limit)}
        >
          Next →
        </button>
      </div>
    </div>
  );
}

function HitCard({ hit, onTriage }) {
  const [expanded, setExpanded] = useState(false);
  const [note, setNote] = useState(hit.triage_note || "");

  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs text-nvidia">{hit.probe}</span>
            <span className="tag">{hit.detector}</span>
            {hit.score != null && (
              <span className="text-[11px] text-danger font-mono">score {hit.score}</span>
            )}
            {hit.turns && (
              <span className="tag flex items-center gap-1">
                <MessagesSquare size={11} /> {hit.turns.length} turns
              </span>
            )}
          </div>
          <div className="text-sm text-ink-muted line-clamp-2 font-mono">
            {hit.prompt}
          </div>
        </div>
        <StatusBadge status={hit.triage_status} />
      </div>

      <button
        className="text-xs text-nvidia mt-2 hover:underline"
        onClick={() => setExpanded((e) => !e)}
      >
        {expanded ? "Hide detail" : "Show prompt / output / triage"}
      </button>

      {expanded && (
        <div className="mt-3 space-y-3">
          <div>
            <div className="label">Prompt</div>
            <pre className="bg-bg-base border border-line rounded p-3 text-xs whitespace-pre-wrap max-h-48 overflow-y-auto">
              {hit.prompt}
            </pre>
          </div>
          <div>
            <div className="label">Model output</div>
            <pre className="bg-bg-base border border-line rounded p-3 text-xs whitespace-pre-wrap max-h-48 overflow-y-auto">
              {hit.output || "(empty)"}
            </pre>
          </div>

          {hit.turns && <ConversationReplay turns={hit.turns} />}

          <div className="flex items-center gap-2 flex-wrap">
            {TRIAGE_OPTIONS.map((o) => (
              <button
                key={o.value}
                onClick={() => onTriage(hit.id, { triage_status: o.value })}
                className={`text-xs px-2.5 py-1 rounded border ${
                  hit.triage_status === o.value
                    ? "border-nvidia text-nvidia bg-nvidia/5"
                    : "border-line text-ink-muted hover:text-ink"
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              className="input"
              placeholder="Analyst note…"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
            <button
              className="btn-ghost"
              onClick={() => onTriage(hit.id, { triage_note: note })}
            >
              Save note
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}

function ConversationReplay({ turns }) {
  return (
    <div>
      <div className="label">Conversation replay</div>
      <div className="space-y-2 max-h-72 overflow-y-auto">
        {turns.map((t, i) => {
          const role = t.role || t.speaker || (i % 2 === 0 ? "attacker" : "target");
          const content =
            typeof t === "string" ? t : t.content || t.text || JSON.stringify(t);
          const isTarget = /assistant|target|model/i.test(role);
          return (
            <div
              key={i}
              className={`text-xs p-2 rounded border font-mono whitespace-pre-wrap ${
                isTarget
                  ? "bg-bg-elevated border-line"
                  : "bg-nvidia/5 border-nvidia/20"
              }`}
            >
              <span className="text-[10px] uppercase text-ink-muted">{role}</span>
              <div className="mt-1">{content}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
