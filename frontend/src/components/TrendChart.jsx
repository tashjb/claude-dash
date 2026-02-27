export function TrendChart({ data, kpi }) {
  const points = data.data || [];

  if (points.length === 0) {
    return <div className="chart-empty">No trend data available for this metric yet.</div>;
  }

  const W = 700, H = 180;
  const pad = { top: 20, right: 20, bottom: 40, left: 50 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;

  const values = points.map((p) => p.value);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1;

  const scaleX = (i) => pad.left + (i / Math.max(points.length - 1, 1)) * innerW;
  const scaleY = (v) => pad.top + innerH - ((v - minVal) / range) * innerH;

  const pathD = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${scaleX(i).toFixed(1)},${scaleY(p.value).toFixed(1)}`)
    .join(" ");

  const areaD =
    pathD +
    ` L${scaleX(points.length - 1).toFixed(1)},${(pad.top + innerH).toFixed(1)}` +
    ` L${pad.left},${(pad.top + innerH).toFixed(1)} Z`;

  // Target line
  const targetVal = parseFloat(kpi.target?.replace(/[^\d.]/g, ""));
  const showTarget = !isNaN(targetVal) && targetVal >= minVal && targetVal <= maxVal + range * 0.2;
  const targetY = showTarget ? scaleY(targetVal) : null;

  // X-axis labels (show ~5 evenly spaced)
  const labelStep = Math.max(1, Math.floor(points.length / 5));
  const xLabels = points.filter((_, i) => i % labelStep === 0 || i === points.length - 1);

  const ragColor = {
    green: "#22c55e",
    amber: "#f59e0b",
    red: "#ef4444",
    grey: "#6b7280",
  }[kpi.rag] || "#6b7280";

  return (
    <div className="chart-container">
      <svg viewBox={`0 0 ${W} ${H}`} className="trend-svg">
        <defs>
          <linearGradient id="areaGrad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={ragColor} stopOpacity="0.25" />
            <stop offset="100%" stopColor={ragColor} stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((t) => {
          const y = pad.top + t * innerH;
          const v = maxVal - t * range;
          return (
            <g key={t}>
              <line x1={pad.left} x2={pad.left + innerW} y1={y} y2={y}
                stroke="#1e2a3a" strokeWidth="1" />
              <text x={pad.left - 6} y={y + 4} textAnchor="end" className="chart-axis-text">
                {v.toFixed(1)}
              </text>
            </g>
          );
        })}

        {/* Target line */}
        {showTarget && targetY && (
          <g>
            <line x1={pad.left} x2={pad.left + innerW} y1={targetY} y2={targetY}
              stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="6 3" />
            <text x={pad.left + innerW + 4} y={targetY + 4} className="chart-target-text">
              target
            </text>
          </g>
        )}

        {/* Area */}
        <path d={areaD} fill="url(#areaGrad)" />

        {/* Line */}
        <path d={pathD} fill="none" stroke={ragColor} strokeWidth="2.5"
          strokeLinecap="round" strokeLinejoin="round" />

        {/* Data points */}
        {points.map((p, i) => (
          <circle
            key={i}
            cx={scaleX(i)}
            cy={scaleY(p.value)}
            r={points.length > 30 ? 1.5 : 3}
            fill={ragColor}
            stroke="#0a1628"
            strokeWidth="1.5"
          >
            <title>{`${p.date}: ${p.value}${kpi.unit}`}</title>
          </circle>
        ))}

        {/* X-axis labels */}
        {xLabels.map((p) => {
          const i = points.indexOf(p);
          return (
            <text key={i} x={scaleX(i)} y={H - 8} textAnchor="middle" className="chart-axis-text">
              {p.date.slice(5)}
            </text>
          );
        })}

        {/* Axes */}
        <line x1={pad.left} x2={pad.left} y1={pad.top} y2={pad.top + innerH}
          stroke="#2a3a50" strokeWidth="1" />
        <line x1={pad.left} x2={pad.left + innerW} y1={pad.top + innerH} y2={pad.top + innerH}
          stroke="#2a3a50" strokeWidth="1" />
      </svg>

      <div className="chart-stats">
        <div className="stat">
          <span className="stat-lbl">Current</span>
          <span className="stat-val">{values[values.length - 1]?.toFixed(1)}{kpi.unit}</span>
        </div>
        <div className="stat">
          <span className="stat-lbl">Min (90d)</span>
          <span className="stat-val">{minVal.toFixed(1)}{kpi.unit}</span>
        </div>
        <div className="stat">
          <span className="stat-lbl">Max (90d)</span>
          <span className="stat-val">{maxVal.toFixed(1)}{kpi.unit}</span>
        </div>
        <div className="stat">
          <span className="stat-lbl">Data Points</span>
          <span className="stat-val">{points.length}</span>
        </div>
      </div>
    </div>
  );
}
