import { useState, useEffect } from "react";

export function SyncLog({ apiBase }) {
  const [log, setLog] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${apiBase}/metrics/sync-log?limit=100`)
      .then((r) => r.json())
      .then((d) => { setLog(d.log); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">Loading sync log…</div>;

  return (
    <div className="log-page">
      <div className="page-header">
        <h2>Sync Log</h2>
        <p>History of all data sync operations.</p>
      </div>

      {log.length === 0 ? (
        <div className="log-empty">No sync history yet. Run a sync from the Connectors tab.</div>
      ) : (
        <table className="log-table">
          <thead>
            <tr>
              <th>Time (UTC)</th>
              <th>Connector</th>
              <th>Status</th>
              <th>Records</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {log.map((entry) => (
              <tr key={entry.id} className={`log-row log-${entry.status}`}>
                <td className="log-time">{entry.synced_at}</td>
                <td><span className="log-connector">{entry.connector}</span></td>
                <td>
                  <span className={`log-status-badge ${entry.status}`}>
                    {entry.status === "success" ? "✓ Success" : "✗ Error"}
                  </span>
                </td>
                <td>{entry.records_synced ?? "—"}</td>
                <td className="log-msg">{entry.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
