import { Link } from "react-router-dom";

export function Page({ title, subtitle, actions, children }) {
  return (
    <div className="px-8 py-6 max-w-[1400px] mx-auto">
      <header className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          {subtitle && <p className="text-sm text-ink-muted mt-1">{subtitle}</p>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </header>
      {children}
    </div>
  );
}

export function Card({ children, className = "" }) {
  return <div className={`card p-5 ${className}`}>{children}</div>;
}

export function Stat({ label, value, tone = "default", sub }) {
  const toneClass = {
    default: "text-ink",
    good: "text-nvidia",
    warn: "text-warn",
    bad: "text-danger",
  }[tone];
  return (
    <div className="card p-4">
      <div className="label">{label}</div>
      <div className={`text-2xl font-semibold font-mono ${toneClass}`}>{value}</div>
      {sub && <div className="text-xs text-ink-muted mt-1">{sub}</div>}
    </div>
  );
}

const STATUS_STYLE = {
  queued: "bg-bg-elevated text-ink-muted",
  running: "bg-nvidia/15 text-nvidia",
  parsing: "bg-nvidia/15 text-nvidia",
  completed: "bg-nvidia/15 text-nvidia",
  failed: "bg-danger/15 text-danger",
  cancelled: "bg-warn/15 text-warn",
  new: "bg-bg-elevated text-ink-muted",
  confirmed: "bg-danger/15 text-danger",
  false_positive: "bg-bg-elevated text-ink-muted",
  accepted_risk: "bg-warn/15 text-warn",
};

export function StatusBadge({ status }) {
  return (
    <span
      className={`text-[11px] px-2 py-0.5 rounded font-medium ${
        STATUS_STYLE[status] || "bg-bg-elevated text-ink-muted"
      }`}
    >
      {String(status || "unknown").replace("_", " ")}
    </span>
  );
}

export function Meter({ value, max = 100, tone = "nvidia" }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const barColor = { nvidia: "bg-nvidia", warn: "bg-warn", danger: "bg-danger" }[tone];
  return (
    <div className="h-1.5 w-full bg-bg-elevated rounded-full overflow-hidden">
      <div className={`h-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function ScoreTone(score) {
  if (score == null) return "default";
  if (score >= 90) return "good";
  if (score >= 70) return "warn";
  return "bad";
}

export function Empty({ children }) {
  return (
    <div className="card p-10 text-center text-ink-muted text-sm">{children}</div>
  );
}

export function LinkButton({ to, children, primary }) {
  return (
    <Link to={to} className={primary ? "btn-primary" : "btn-ghost"}>
      {children}
    </Link>
  );
}
