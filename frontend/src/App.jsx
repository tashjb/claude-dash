import { useState, useEffect } from "react";
import { KPICard } from "./components/KPICard";
import { TrendChart } from "./components/TrendChart";
import { ConnectorStatus } from "./components/ConnectorStatus";
import { UploadPanel } from "./components/UploadPanel";
import { SyncLog } from "./components/SyncLog";

const API = "http://localhost:8000/api";

const DOMAIN_LABELS = {
  vulnerability_management: "Vulnerability Mgmt",
  endpoint_protection: "Endpoint Protection",
  identity_access: "Identity & Access",
  incident_response: "Incident Response",
  phishing_awareness: "Phishing & Awareness",
  compliance: "Compliance Posture",
};

const DOMAIN_ICONS = {
  vulnerability_management: "⬡",
  endpoint_protection: "◈",
  identity_access: "⌘",
  incident_response: "◉",
  phishing_awareness: "◎",
  compliance: "▣",
};

export default function App() {
  const [kpis, setKpis] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [selectedKpi, setSelectedKpi] = useState(null);
  const [trendData, setTrendData] = useState(null);
  const [connectors, setConnectors] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [error, setError] = useState(null);

  async function fetchKpis() {
    try {
      const res = await fetch(`${API}/metrics/kpis`);
      const data = await res.json();
      setKpis(data);
      setLastRefresh(new Date());
      setError(null);
    } catch (e) {
      setError("Cannot reach backend. Is the server running on port 8000?");
    }
  }

  async function fetchConnectors() {
    try {
      const res = await fetch(`${API}/connectors/status`);
      setConnectors(await res.json());
    } catch (e) {}
  }

  async function fetchTrend(domain, key) {
    try {
      const res = await fetch(`${API}/metrics/trend/${domain}/${key}?days=90`);
      const data = await res.json();
      setTrendData(data);
    } catch (e) {}
  }

  async function syncAll() {
    setSyncing(true);
    try {
      await fetch(`${API}/connectors/sync/all`, { method: "POST" });
      await fetchKpis();
      await fetchConnectors();
    } finally {
      setSyncing(false);
    }
  }

  useEffect(() => {
    fetchKpis();
    fetchConnectors();
    const iv = setInterval(fetchKpis, 5 * 60 * 1000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    if (selectedKpi) {
      fetchTrend(selectedKpi.domain, selectedKpi.metric_key);
    }
  }, [selectedKpi]);

  const domains = kpis
    ? [...new Set(kpis.kpis.map((k) => k.domain))]
    : [];

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <span className="logo-mark">◈</span>
            <div>
              <div className="logo-title">SecureMetrics</div>
              <div className="logo-sub">Financial Services Security Program</div>
            </div>
          </div>
        </div>
        <nav className="nav">
          {["overview", "connectors", "upload", "log"].map((tab) => (
            <button
              key={tab}
              className={`nav-btn ${activeTab === tab ? "active" : ""}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>
        <div className="header-right">
          {lastRefresh && (
            <span className="refresh-time">
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button className={`sync-btn ${syncing ? "syncing" : ""}`} onClick={syncAll}>
            {syncing ? "Syncing…" : "↻ Sync All"}
          </button>
        </div>
      </header>

      <main className="main">
        {error && (
          <div className="error-banner">
            <strong>Connection Error</strong> — {error}
          </div>
        )}

        {/* ── Overview Tab ── */}
        {activeTab === "overview" && (
          <>
            {/* Program health bar */}
            {kpis && (
              <div className="health-bar">
                <div className="health-scores">
                  <div className="health-item green">
                    <span className="h-num">{kpis.summary.green}</span>
                    <span className="h-lbl">On Target</span>
                  </div>
                  <div className="health-item amber">
                    <span className="h-num">{kpis.summary.amber}</span>
                    <span className="h-lbl">At Risk</span>
                  </div>
                  <div className="health-item red">
                    <span className="h-num">{kpis.summary.red}</span>
                    <span className="h-lbl">Critical</span>
                  </div>
                  <div className="health-item grey">
                    <span className="h-num">{kpis.summary.grey}</span>
                    <span className="h-lbl">No Data</span>
                  </div>
                </div>
                <div className="health-overall">
                  <div className="health-label">Program Health</div>
                  <div className="health-gauge">
                    <div
                      className="health-fill"
                      style={{ width: `${kpis.summary.overall_health}%` }}
                    />
                  </div>
                  <div className="health-pct">{kpis.summary.overall_health}%</div>
                </div>
              </div>
            )}

            {/* KPI grid by domain */}
            {!kpis && !error && (
              <div className="loading">Loading metrics…</div>
            )}

            {kpis && domains.map((domain) => (
              <section key={domain} className="domain-section">
                <h2 className="domain-title">
                  <span className="domain-icon">{DOMAIN_ICONS[domain]}</span>
                  {DOMAIN_LABELS[domain] || domain}
                </h2>
                <div className="kpi-grid">
                  {kpis.kpis
                    .filter((k) => k.domain === domain)
                    .map((kpi) => (
                      <KPICard
                        key={kpi.id}
                        kpi={kpi}
                        selected={selectedKpi?.id === kpi.id}
                        onClick={() => setSelectedKpi(selectedKpi?.id === kpi.id ? null : kpi)}
                      />
                    ))}
                </div>
              </section>
            ))}

            {/* Trend panel */}
            {selectedKpi && trendData && (
              <div className="trend-panel">
                <div className="trend-header">
                  <h3>{selectedKpi.label} — 90-Day Trend</h3>
                  <button className="close-btn" onClick={() => setSelectedKpi(null)}>✕</button>
                </div>
                <TrendChart data={trendData} kpi={selectedKpi} />
              </div>
            )}
          </>
        )}

        {activeTab === "connectors" && (
          <ConnectorStatus connectors={connectors} onSync={fetchConnectors} apiBase={API} />
        )}

        {activeTab === "upload" && (
          <UploadPanel apiBase={API} onUploaded={fetchKpis} />
        )}

        {activeTab === "log" && (
          <SyncLog apiBase={API} />
        )}
      </main>
    </div>
  );
}
