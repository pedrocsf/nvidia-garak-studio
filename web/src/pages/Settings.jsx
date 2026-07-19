import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Key, Trash2, Upload, ShieldCheck } from "lucide-react";
import { api } from "../lib/api";
import { Page, Card, Empty } from "../components/ui";

export default function Settings() {
  const qc = useQueryClient();

  const { data: info } = useQuery({ queryKey: ["info"], queryFn: api.info });
  const { data: secrets = [] } = useQuery({
    queryKey: ["secrets"],
    queryFn: api.secrets,
  });

  const [form, setForm] = useState({ name: "", env_var: "", value: "" });
  const [importing, setImporting] = useState(false);

  async function saveSecret(e) {
    e.preventDefault();
    if (!form.name || !form.env_var || !form.value) return;
    await api.createSecret(form);
    setForm({ name: "", env_var: "", value: "" });
    qc.invalidateQueries({ queryKey: ["secrets"] });
  }

  async function removeSecret(id) {
    await api.deleteSecret(id);
    qc.invalidateQueries({ queryKey: ["secrets"] });
  }

  async function importReport(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(
        `/api/reports/import?label=${encodeURIComponent(file.name)}`,
        { method: "POST", body: fd }
      );
      if (!res.ok) throw new Error(await res.text());
      qc.invalidateQueries({ queryKey: ["runs"] });
      alert("Report imported.");
    } catch (err) {
      alert(`Import failed: ${err.message}`);
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  }

  return (
    <Page title="Settings" subtitle="Credentials, imports, and environment">
      <div className="grid grid-cols-2 gap-5">
        <Card>
          <h3 className="text-sm font-semibold mb-1 flex items-center gap-2">
            <Key size={15} /> API keys & secrets
          </h3>
          <p className="text-xs text-ink-muted mb-4">
            Stored encrypted at rest and injected into scan processes as
            environment variables. Never returned to the browser after saving.
          </p>

          <form onSubmit={saveSecret} className="space-y-2 mb-5">
            <input
              className="input"
              placeholder="Name (e.g. OpenAI prod)"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <input
              className="input font-mono"
              placeholder="Env var (e.g. OPENAI_API_KEY)"
              value={form.env_var}
              onChange={(e) => setForm({ ...form, env_var: e.target.value })}
            />
            <input
              className="input font-mono"
              type="password"
              placeholder="Secret value"
              value={form.value}
              onChange={(e) => setForm({ ...form, value: e.target.value })}
            />
            <button className="btn-primary" type="submit">
              Save secret
            </button>
          </form>

          {secrets.length === 0 ? (
            <Empty>No secrets stored.</Empty>
          ) : (
            <div className="space-y-2">
              {secrets.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between p-2.5 rounded border border-line"
                >
                  <div>
                    <div className="text-sm">{s.name}</div>
                    <div className="text-[11px] text-ink-muted font-mono">
                      {s.env_var} = {s.hint}
                    </div>
                  </div>
                  <button
                    className="text-ink-muted hover:text-danger"
                    onClick={() => removeSecret(s.id)}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>

        <div className="space-y-5">
          <Card>
            <h3 className="text-sm font-semibold mb-1 flex items-center gap-2">
              <Upload size={15} /> Import external report
            </h3>
            <p className="text-xs text-ink-muted mb-3">
              Load a <span className="font-mono">*.report.jsonl</span> produced by
              garak elsewhere (CLI, another server) to centralize history.
            </p>
            <label className="btn-ghost cursor-pointer inline-flex">
              <Upload size={15} /> {importing ? "Importing…" : "Choose JSONL file"}
              <input
                type="file"
                accept=".jsonl"
                className="hidden"
                onChange={importReport}
                disabled={importing}
              />
            </label>
          </Card>

          <Card>
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <ShieldCheck size={15} /> Environment
            </h3>
            <dl className="text-sm space-y-2">
              <div className="flex justify-between">
                <dt className="text-ink-muted">garak available</dt>
                <dd className={info?.garak_available ? "text-nvidia" : "text-danger"}>
                  {info?.garak_available ? "yes" : "no"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-muted">garak version</dt>
                <dd className="font-mono">{info?.garak_version || "—"}</dd>
              </div>
            </dl>
          </Card>
        </div>
      </div>
    </Page>
  );
}
