import { useState } from "react";

const CONNECTOR_INFO = {
  microsoft_defender: {
    name: "Microsoft Defender",
    icon: "◈",
    description: "Endpoint protection, vulnerability exposure, and Secure Score",
    docs: "https://docs.microsoft.com/en-us/microsoft-365/security/defender-endpoint/",
    configKeys: ["tenant_id", "client_id", "client_secret"],
  },
  okta: {
    name: "Okta",
    icon: "⌘",
    description: "MFA enrollment, user lifecycle, orphan accounts, admin access",
    docs: "https://developer.okta.com/docs/reference/core-okta-api/",
    configKeys: ["domain", "api_token"],
  },
  spreadsheet: {
    name: "Spreadsheets (Excel/CSV)",
    icon: "▦",
    description: "Manual metric ingestion from Excel or CSV files",
    docs: null,
    configKeys: ["watch_directory"],
  },
};

export function ConnectorStatus({ connectors, onSync, apiBase }) {
  const [syncingOne, setSyncingOne] = useState(null);
  const [syncResult, setSyncResult] = useState({});

  async function syncConnector(name) {
    setSyncingOne(name);
    try {
      const res = await fetch(`${apiBase}/connectors/sync/${name}`, { method: "POST" });
      const data = await res.json();
      setSyncResult((prev) => ({ ...prev, [name]: data }));
      onSync();
    } catch (e) {
      setSyncResult((prev) => ({ ...prev, [name]: { status: "error", error: e.message } }));
    } finally {
      setSyncingOne(null);
    }
  }

  if (!connectors) return <div className="loading">Loading connector status…</div>;

  return (
    <div className="connectors-page">
      <div className="page-header">
        <h2>Data Connectors</h2>
        <p>Manage API integrations and data sources. Configure credentials in <code>config.yaml</code>.</p>
      </div>

      <div className="connector-list">
        {Object.entries(CONNECTOR_INFO).map(([name, info]) => {
          const status = connectors[name];
          const isEnabled = status?.enabled || name === "spreadsheet";
          const lastSync = status?.last_sync;
          const result = syncResult[name];

          return (
            <div key={name} className={`connector-card ${isEnabled ? "enabled" : "disabled"}`}>
              <div className="connector-icon">{info.icon}</div>
              <div className="connector-body">
                <div className="connector-name-row">
                  <span className="connector-name">{info.name}</span>
                  <span className={`connector-badge ${isEnabled ? "badge-enabled" : "badge-disabled"}`}>
                    {isEnabled ? "Enabled" : "Disabled"}
                  </span>
                </div>
                <p className="connector-desc">{info.description}</p>

                {lastSync && (
                  <div className={`last-sync sync-${lastSync.status}`}>
                    Last sync: {lastSync.synced_at} —{" "}
                    {lastSync.status === "success"
                      ? `✓ ${lastSync.records_synced} records`
                      : `✗ ${lastSync.message}`}
                  </div>
                )}

                {result && (
                  <div className={`sync-result ${result.status === "success" ? "ok" : "err"}`}>
                    {result.status === "success"
                      ? `✓ Synced ${result.records_synced ?? result.total_records_ingested ?? 0} records`
                      : `✗ ${result.detail || result.error}`}
                  </div>
                )}

                {!isEnabled && (
                  <div className="config-hint">
                    Add credentials to <code>config.yaml</code> under <code>connectors.{name}</code>
                    {info.docs && (
                      <> — <a href={info.docs} target="_blank" rel="noreferrer">API docs ↗</a></>
                    )}
                  </div>
                )}
              </div>
              <button
                className="connector-sync-btn"
                onClick={() => syncConnector(name)}
                disabled={syncingOne === name || (!isEnabled && name !== "spreadsheet")}
              >
                {syncingOne === name ? "Syncing…" : "Sync Now"}
              </button>
            </div>
          );
        })}
      </div>

      <div className="config-tip">
        <h3>Adding a New Connector</h3>
        <ol>
          <li>Create <code>backend/connectors/your_tool.py</code> following the existing connector pattern</li>
          <li>Register it in <code>backend/connectors/__init__.py</code></li>
          <li>Add credentials to <code>config.yaml</code></li>
          <li>Restart the backend and it will appear here automatically</li>
        </ol>
      </div>
    </div>
  );
}
