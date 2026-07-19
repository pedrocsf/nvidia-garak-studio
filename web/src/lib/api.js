async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      detail = res.statusText;
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

export const api = {
  health: () => request("/health"),
  info: () => request("/settings/info"),

  discoverySupported: () => request("/discovery/supported"),
  discoverModels: (type, params = {}) => {
    const q = new URLSearchParams({ type, ...params }).toString();
    return request(`/discovery/models?${q}`);
  },

  pluginSummary: () => request("/plugins/summary"),
  plugins: (category, meta = true) =>
    request(`/plugins/${category}?meta=${meta}`),
  refreshPlugins: () => request("/plugins/refresh", { method: "POST" }),

  estimate: (config) =>
    request("/scans/estimate", { method: "POST", body: JSON.stringify({ config }) }),
  createScan: (payload) =>
    request("/scans", { method: "POST", body: JSON.stringify(payload) }),
  runs: (status) => request(`/runs${status ? `?status=${status}` : ""}`),
  run: (id) => request(`/runs/${id}`),
  runResults: (id) => request(`/runs/${id}/results`),
  cancelRun: (id) => request(`/runs/${id}/cancel`, { method: "POST" }),
  riskMatrix: (id) => request(`/runs/${id}/risk-matrix`),

  hits: (id, params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request(`/reports/${id}/hits${q ? `?${q}` : ""}`);
  },
  hitCount: (id) => request(`/reports/${id}/hits/count`),

  compare: (a, b) => request(`/compare?a=${a}&b=${b}`),

  updateTriage: (hitId, body) =>
    request(`/triage/hits/${hitId}`, { method: "PATCH", body: JSON.stringify(body) }),
  triageQueue: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request(`/triage/queue${q ? `?${q}` : ""}`);
  },
  triageStats: () => request("/triage/stats"),

  profiles: () => request("/scans/profiles"),
  createProfile: (body) =>
    request("/scans/profiles", { method: "POST", body: JSON.stringify(body) }),
  deleteProfile: (id) => request(`/scans/profiles/${id}`, { method: "DELETE" }),

  secrets: () => request("/settings/secrets"),
  createSecret: (body) =>
    request("/settings/secrets", { method: "POST", body: JSON.stringify(body) }),
  deleteSecret: (id) => request(`/settings/secrets/${id}`, { method: "DELETE" }),
};

export function runSocketUrl(runId) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/runs/${runId}`;
}
