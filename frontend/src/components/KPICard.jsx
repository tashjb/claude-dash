export function KPICard({ kpi, selected, onClick }) {
  const hasData = kpi.value !== null && kpi.value !== undefined;

  return (
    <div
      className={`kpi-card rag-${kpi.rag} ${selected ? "selected" : ""} ${!hasData ? "no-data" : ""}`}
      onClick={onClick}
      title={kpi.description}
    >
      <div className="kpi-top">
        <span className="kpi-label">{kpi.label}</span>
        <span className={`rag-dot rag-${kpi.rag}`} />
      </div>

      <div className="kpi-value">
        {hasData ? (
          <>
            <span className="kpi-num">{formatValue(kpi.value, kpi.unit)}</span>
            <span className="kpi-unit">{kpi.unit}</span>
          </>
        ) : (
          <span className="kpi-no-data">—</span>
        )}
      </div>

      <div className="kpi-bottom">
        <span className="kpi-target">Target: {kpi.target}</span>
        {kpi.rag !== "grey" && (
          <span className={`kpi-status-text rag-${kpi.rag}`}>
            {kpi.rag === "green" ? "On Target" : kpi.rag === "amber" ? "At Risk" : "Critical"}
          </span>
        )}
      </div>

      {hasData && (
        <div className="kpi-bar-track">
          <div
            className={`kpi-bar-fill rag-${kpi.rag}`}
            style={{ width: `${barWidth(kpi)}%` }}
          />
        </div>
      )}
    </div>
  );
}

function formatValue(value, unit) {
  if (value === null || value === undefined) return "—";
  if (unit === "%" || unit === "/100") return value.toFixed(1);
  if (unit === "days" || unit === "hrs") return value.toFixed(1);
  return Math.round(value).toLocaleString();
}

function barWidth(kpi) {
  if (kpi.value === null) return 0;
  if (kpi.unit === "%" || kpi.unit === "/100") return Math.min(100, kpi.value);
  // For rates/counts, use a rough proportion vs target
  return Math.min(100, 50); // fallback
}
