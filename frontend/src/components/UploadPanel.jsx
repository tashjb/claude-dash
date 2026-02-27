import { useState, useRef } from "react";

const TEMPLATE_CSV = `domain,metric_key,metric_value,metric_label,snapshot_date,source
vulnerability_management,patch_compliance_pct,97.2,,2024-01-15,Patching Tool
vulnerability_management,critical_vuln_mttr_days,12.5,,2024-01-15,Patching Tool
endpoint_protection,endpoint_coverage_pct,99.1,,2024-01-15,MDM Report
identity_access,mfa_enrollment_pct,98.4,,2024-01-15,Okta Export
identity_access,orphan_account_pct,0.8,,2024-01-15,HR Reconciliation
incident_response,mttd_hours,3.2,,2024-01-15,SOC Report
incident_response,mttr_hours,18.7,,2024-01-15,SOC Report
phishing_awareness,click_rate_pct,2.9,,2024-01-15,KnowBe4
phishing_awareness,training_completion_pct,96.5,,2024-01-15,LMS Export
compliance,controls_coverage_pct,94.2,,2024-01-15,GRC Tool
`;

export function UploadPanel({ apiBase, onUploaded }) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const fileRef = useRef();

  async function uploadFile(file) {
    setUploading(true);
    setResult(null);
    setError(null);

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await fetch(`${apiBase}/connectors/upload`, {
        method: "POST",
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed");
      setResult(data);
      onUploaded();
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  }

  function downloadTemplate() {
    const blob = new Blob([TEMPLATE_CSV], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "security_metrics_template.csv";
    a.click();
  }

  return (
    <div className="upload-page">
      <div className="page-header">
        <h2>Upload Metrics Spreadsheet</h2>
        <p>Import security metrics from Excel (.xlsx) or CSV files. Use the template below to get started.</p>
      </div>

      <div
        className={`drop-zone ${dragging ? "drag-over" : ""} ${uploading ? "uploading" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          style={{ display: "none" }}
          onChange={(e) => e.target.files[0] && uploadFile(e.target.files[0])}
        />
        <div className="drop-icon">{uploading ? "⟳" : "↑"}</div>
        <div className="drop-text">
          {uploading ? "Uploading…" : "Drop a file here or click to browse"}
        </div>
        <div className="drop-sub">.xlsx, .xls, or .csv</div>
      </div>

      {result && (
        <div className="upload-success">
          <strong>✓ Imported successfully</strong> — {result.records_ingested} metrics from{" "}
          <em>{result.file}</em>. The dashboard will reflect the new data.
        </div>
      )}

      {error && (
        <div className="upload-error">
          <strong>✗ Import failed</strong> — {error}
        </div>
      )}

      <div className="template-section">
        <h3>CSV Template</h3>
        <p>
          Your spreadsheet must include: <code>domain</code>, <code>metric_key</code>, <code>metric_value</code>.
          Optional: <code>metric_label</code>, <code>snapshot_date</code>, <code>source</code>.
        </p>

        <div className="domain-table">
          <h4>Valid Domains</h4>
          <table>
            <thead><tr><th>Domain Value</th><th>Description</th></tr></thead>
            <tbody>
              {[
                ["vulnerability_management", "Patch rates, MTTR, open vulns"],
                ["endpoint_protection", "EDR coverage, agent health"],
                ["identity_access", "MFA, orphan accounts, admin ratios"],
                ["incident_response", "MTTD, MTTR, open incidents"],
                ["phishing_awareness", "Click rates, training completion"],
                ["compliance", "Controls coverage, audit findings, Secure Score"],
              ].map(([d, desc]) => (
                <tr key={d}><td><code>{d}</code></td><td>{desc}</td></tr>
              ))}
            </tbody>
          </table>
        </div>

        <button className="download-btn" onClick={downloadTemplate}>
          ↓ Download CSV Template
        </button>

        <div className="csv-preview">
          <pre>{TEMPLATE_CSV}</pre>
        </div>
      </div>
    </div>
  );
}
