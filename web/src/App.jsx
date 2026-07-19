import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import {
  LayoutDashboard,
  PlusCircle,
  ListChecks,
  GitCompareArrows,
  ShieldAlert,
  Boxes,
  Settings as SettingsIcon,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./lib/api";

import Dashboard from "./pages/Dashboard";
import ScanBuilder from "./pages/ScanBuilder";
import LiveRun from "./pages/LiveRun";
import Runs from "./pages/Runs";
import Report from "./pages/Report";
import Compare from "./pages/Compare";
import Triage from "./pages/Triage";
import Plugins from "./pages/Plugins";
import Settings from "./pages/Settings";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/scan", label: "New Scan", icon: PlusCircle },
  { to: "/runs", label: "Runs", icon: ListChecks },
  { to: "/compare", label: "Compare", icon: GitCompareArrows },
  { to: "/triage", label: "Triage", icon: ShieldAlert },
  { to: "/plugins", label: "Plugins", icon: Boxes },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

function Sidebar() {
  const { data: info } = useQuery({ queryKey: ["info"], queryFn: api.info });
  return (
    <aside className="w-56 shrink-0 border-r border-line bg-bg-panel flex flex-col">
      <div className="px-5 py-5 border-b border-line">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-sm bg-nvidia" />
          <span className="font-semibold tracking-tight">Garak Studio</span>
        </div>
        <div className="mt-1 text-[11px] text-ink-muted font-mono">
          {info?.garak_available
            ? `garak ${info.garak_version}`
            : "garak not detected"}
        </div>
      </div>
      <nav className="flex-1 py-3">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
                isActive
                  ? "text-ink bg-bg-elevated border-l-2 border-nvidia"
                  : "text-ink-muted hover:text-ink border-l-2 border-transparent"
              }`
            }
          >
            <Icon size={17} strokeWidth={1.75} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-3 text-[10px] text-ink-muted border-t border-line">
        LLM vulnerability scanning
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/scan" element={<ScanBuilder />} />
          <Route path="/runs" element={<Runs />} />
          <Route path="/runs/:runId/live" element={<LiveRun />} />
          <Route path="/runs/:runId" element={<Report />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/triage" element={<Triage />} />
          <Route path="/plugins" element={<Plugins />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
