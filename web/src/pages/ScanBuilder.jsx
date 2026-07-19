import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Search,
  Check,
  ChevronRight,
  ChevronLeft,
  Zap,
  RefreshCw,
  Keyboard,
  List,
} from "lucide-react";
import { api } from "../lib/api";
import { Page, Card } from "../components/ui";

const STEPS = ["Target", "Probes & Detectors", "Buffs & Harness", "Review"];

function StepBar({ step }) {
  return (
    <div className="flex items-center gap-2 mb-6">
      {STEPS.map((s, i) => (
        <div key={s} className="flex items-center gap-2">
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs ${
              i === step
                ? "bg-nvidia text-black font-medium"
                : i < step
                ? "text-nvidia"
                : "text-ink-muted"
            }`}
          >
            {i < step ? <Check size={13} /> : <span className="font-mono">{i + 1}</span>}
            {s}
          </div>
          {i < STEPS.length - 1 && <ChevronRight size={14} className="text-line" />}
        </div>
      ))}
    </div>
  );
}

function PluginPicker({ category, selected, onToggle }) {
  const [q, setQ] = useState("");
  const { data = [], isLoading } = useQuery({
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
        (p.tags || []).some((t) => t.toLowerCase().includes(needle))
    );
  }, [data, q]);

  return (
    <div>
      <div className="relative mb-3">
        <Search size={15} className="absolute left-3 top-2.5 text-ink-muted" />
        <input
          className="input pl-9"
          placeholder={`Search ${category}… (name or tag, e.g. owasp:llm01)`}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      {isLoading ? (
        <div className="text-ink-muted text-sm p-4">Loading {category} from garak…</div>
      ) : (
        <div className="max-h-[420px] overflow-y-auto space-y-1 pr-1">
          {filtered.map((p) => {
            const short = p.name.replace(`${category}.`, "");
            const isSel = selected.includes(short);
            return (
              <button
                key={p.name}
                onClick={() => onToggle(short)}
                className={`w-full text-left p-3 rounded-md border transition-colors ${
                  isSel
                    ? "border-nvidia/50 bg-nvidia/5"
                    : "border-line hover:bg-bg-elevated"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm">{short}</span>
                  {isSel && <Check size={14} className="text-nvidia" />}
                </div>
                {p.goal && (
                  <div className="text-xs text-ink-muted mt-1 line-clamp-1">{p.goal}</div>
                )}
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {(p.tags || []).slice(0, 4).map((t) => (
                    <span key={t} className="tag">
                      {t}
                    </span>
                  ))}
                </div>
              </button>
            );
          })}
          {filtered.length === 0 && (
            <div className="text-ink-muted text-sm p-4">No matches.</div>
          )}
        </div>
      )}
    </div>
  );
}

function ModelPicker({ generatorType, value, onChange, baseUrl }) {
  const [manual, setManual] = useState(false);

  const { data: supported } = useQuery({
    queryKey: ["discoverySupported"],
    queryFn: api.discoverySupported,
    staleTime: Infinity,
  });
  const canDiscover = supported?.discoverable?.includes(generatorType);

  const {
    data: discovery,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["discoverModels", generatorType, baseUrl],
    queryFn: () =>
      api.discoverModels(generatorType, baseUrl ? { base_url: baseUrl } : {}),
    enabled: Boolean(canDiscover) && !manual,
    retry: false,
  });

  const models = discovery?.models || [];
  const note = discovery?.note;

  if (!canDiscover) {
    return (
      <input
        className="input mb-4"
        placeholder="e.g. gpt-4o-mini, Blank, llama3"
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }

  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 mb-2">
        <button
          type="button"
          onClick={() => setManual(false)}
          className={`text-xs px-2 py-1 rounded flex items-center gap-1 ${
            !manual ? "bg-bg-elevated text-ink" : "text-ink-muted"
          }`}
        >
          <List size={12} /> Discovered
        </button>
        <button
          type="button"
          onClick={() => setManual(true)}
          className={`text-xs px-2 py-1 rounded flex items-center gap-1 ${
            manual ? "bg-bg-elevated text-ink" : "text-ink-muted"
          }`}
        >
          <Keyboard size={12} /> Manual
        </button>
        {!manual && (
          <button
            type="button"
            onClick={() => refetch()}
            className="text-xs text-ink-muted hover:text-nvidia flex items-center gap-1 ml-auto"
          >
            <RefreshCw size={12} className={isFetching ? "animate-spin" : ""} /> Refresh
          </button>
        )}
      </div>

      {manual ? (
        <input
          className="input"
          placeholder="Type the model name"
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <>
          <select
            className="input"
            value={value || ""}
            onChange={(e) => onChange(e.target.value)}
            disabled={isFetching || models.length === 0}
          >
            <option value="">
              {isFetching
                ? "Discovering…"
                : models.length
                ? "Select a model…"
                : "No models found"}
            </option>
            {models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <div className="text-xs mt-1.5 font-mono">
            {isFetching ? (
              <span className="text-ink-muted">querying {generatorType}…</span>
            ) : models.length ? (
              <span className="text-nvidia">{models.length} models found</span>
            ) : (
              <span className="text-warn">{note || "nothing discovered"}</span>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default function ScanBuilder() {
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const [config, setConfig] = useState({
    generator: { type: "test", name: "Blank", options: {} },
    probes: [],
    detectors: "auto",
    harness: null,
    buffs: [],
    generations: 5,
  });
  const [label, setLabel] = useState("");
  const [estimate, setEstimate] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const { data: generators = [] } = useQuery({
    queryKey: ["plugins", "generators"],
    queryFn: () => api.plugins("generators", true),
    retry: false,
  });

  const toggle = (key, value) =>
    setConfig((c) => {
      const arr = c[key];
      return {
        ...c,
        [key]: arr.includes(value) ? arr.filter((x) => x !== value) : [...arr, value],
      };
    });

  async function runEstimate() {
    const cfg = { ...config, probes: config.probes.length ? config.probes : "all" };
    try {
      setEstimate(await api.estimate(cfg));
    } catch (e) {
      setEstimate({ note: `Estimate unavailable: ${e.message}` });
    }
  }

  async function submit() {
    setSubmitting(true);
    try {
      const cfg = { ...config, probes: config.probes.length ? config.probes : "all" };
      const run = await api.createScan({ label, config: cfg });
      nav(`/runs/${run.id}/live`);
    } catch (e) {
      alert(`Failed to start scan: ${e.message}`);
      setSubmitting(false);
    }
  }

  const genFamilies = useMemo(() => {
    const set = new Map();
    for (const g of generators) {
      const fam = g.name.split(".")[1];
      if (!set.has(fam)) set.set(fam, []);
      set.get(fam).push(g);
    }
    return set;
  }, [generators]);

  return (
    <Page title="New Scan" subtitle="Configure and launch a garak run">
      <StepBar step={step} />

      {step === 0 && (
        <Card>
          <label className="label">Generator / target backend</label>
          <select
            className="input mb-4"
            value={config.generator.type}
            onChange={(e) =>
              setConfig((c) => ({ ...c, generator: { ...c.generator, type: e.target.value } }))
            }
          >
            {[...genFamilies.keys()].sort().map((fam) => (
              <option key={fam} value={fam}>
                {fam}
              </option>
            ))}
          </select>

          <label className="label">Model name</label>
          <ModelPicker
            generatorType={config.generator.type}
            value={config.generator.name}
            onChange={(name) =>
              setConfig((c) => ({ ...c, generator: { ...c.generator, name } }))
            }
          />

          <label className="label">Scan label (optional)</label>
          <input
            className="input"
            placeholder="Nightly regression — prod model"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
          <p className="text-xs text-ink-muted mt-3">
            API keys for remote backends are configured under Settings and injected
            securely at run time.
          </p>
        </Card>
      )}

      {step === 1 && (
        <div className="grid grid-cols-2 gap-5">
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold">Probes</h3>
              <span className="text-xs text-ink-muted">
                {config.probes.length || "all"} selected
              </span>
            </div>
            <PluginPicker
              category="probes"
              selected={config.probes}
              onToggle={(v) => toggle("probes", v)}
            />
            <p className="text-xs text-ink-muted mt-3">
              Select none to run garak's full default probe set.
            </p>
          </Card>
          <Card>
            <h3 className="text-sm font-semibold mb-3">Detectors</h3>
            <label className="flex items-center gap-2 text-sm mb-3">
              <input
                type="radio"
                checked={config.detectors === "auto"}
                onChange={() => setConfig((c) => ({ ...c, detectors: "auto" }))}
              />
              Automatic — use each probe's recommended detectors (probewise)
            </label>
            <label className="flex items-center gap-2 text-sm mb-3">
              <input
                type="radio"
                checked={Array.isArray(config.detectors)}
                onChange={() => setConfig((c) => ({ ...c, detectors: [] }))}
              />
              Manual override
            </label>
            {Array.isArray(config.detectors) && (
              <PluginPicker
                category="detectors"
                selected={config.detectors}
                onToggle={(v) => toggle("detectors", v)}
              />
            )}
          </Card>
        </div>
      )}

      {step === 2 && (
        <div className="grid grid-cols-2 gap-5">
          <Card>
            <h3 className="text-sm font-semibold mb-3">Buffs (prompt transforms)</h3>
            <p className="text-xs text-ink-muted mb-3">
              Optional transforms applied before sending, e.g. paraphrase or
              low-resource-language translation.
            </p>
            <PluginPicker
              category="buffs"
              selected={config.buffs}
              onToggle={(v) => toggle("buffs", v)}
            />
          </Card>
          <Card>
            <h3 className="text-sm font-semibold mb-3">Harness & generations</h3>
            <label className="label">Harness</label>
            <select
              className="input mb-4"
              value={config.harness || ""}
              onChange={(e) =>
                setConfig((c) => ({ ...c, harness: e.target.value || null }))
              }
            >
              <option value="">Default (probewise)</option>
            </select>
            <label className="label">Generations per prompt</label>
            <input
              type="number"
              min="1"
              className="input"
              value={config.generations}
              onChange={(e) =>
                setConfig((c) => ({ ...c, generations: Number(e.target.value) }))
              }
            />
          </Card>
        </div>
      )}

      {step === 3 && (
        <Card>
          <h3 className="text-sm font-semibold mb-4">Review & launch</h3>
          <dl className="grid grid-cols-2 gap-3 text-sm mb-5">
            <div>
              <dt className="label">Target</dt>
              <dd className="font-mono">
                {config.generator.type}:{config.generator.name}
              </dd>
            </div>
            <div>
              <dt className="label">Probes</dt>
              <dd className="font-mono">
                {config.probes.length ? config.probes.join(", ") : "all"}
              </dd>
            </div>
            <div>
              <dt className="label">Detectors</dt>
              <dd className="font-mono">
                {Array.isArray(config.detectors)
                  ? config.detectors.join(", ") || "—"
                  : "auto"}
              </dd>
            </div>
            <div>
              <dt className="label">Buffs</dt>
              <dd className="font-mono">{config.buffs.join(", ") || "none"}</dd>
            </div>
            <div>
              <dt className="label">Generations</dt>
              <dd className="font-mono">{config.generations}</dd>
            </div>
          </dl>

          <div className="flex items-center gap-3 mb-5">
            <button className="btn-ghost" onClick={runEstimate}>
              <Zap size={15} /> Estimate cost / size
            </button>
            {estimate && (
              <div className="text-xs text-ink-muted font-mono">
                {estimate.estimated_generations != null
                  ? `~${estimate.probe_count} probes · ~${estimate.estimated_prompts} prompts · ~${estimate.estimated_generations} generations`
                  : estimate.note}
              </div>
            )}
          </div>
          {estimate?.note && estimate.estimated_generations != null && (
            <p className="text-xs text-warn mb-4">{estimate.note}</p>
          )}

          <button className="btn-primary" disabled={submitting} onClick={submit}>
            {submitting ? "Launching…" : "Launch scan →"}
          </button>
        </Card>
      )}

      <div className="flex items-center justify-between mt-6">
        <button
          className="btn-ghost"
          disabled={step === 0}
          onClick={() => setStep((s) => s - 1)}
        >
          <ChevronLeft size={16} /> Back
        </button>
        {step < STEPS.length - 1 && (
          <button className="btn-primary" onClick={() => setStep((s) => s + 1)}>
            Next <ChevronRight size={16} />
          </button>
        )}
      </div>
    </Page>
  );
}
