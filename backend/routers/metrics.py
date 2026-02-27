from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional
from database import get_db

router = APIRouter()


def row_to_dict(row):
    return dict(row) if row else None


@router.get("/summary")
def get_dashboard_summary():
    """
    Returns the latest value for every key metric across all domains.
    This is the main endpoint for the dashboard overview.
    """
    db = get_db()
    cursor = db.cursor()

    # Get the most recent snapshot date per domain/metric
    cursor.execute("""
        SELECT domain, metric_key, metric_value, metric_label, source, snapshot_date
        FROM metric_snapshots ms
        WHERE snapshot_date = (
            SELECT MAX(snapshot_date) FROM metric_snapshots ms2
            WHERE ms2.domain = ms.domain AND ms2.metric_key = ms.metric_key
        )
        ORDER BY domain, metric_key
    """)
    rows = cursor.fetchall()
    db.close()

    # Organize by domain
    summary = {}
    for row in rows:
        d = row["domain"]
        if d not in summary:
            summary[d] = {}
        summary[d][row["metric_key"]] = {
            "value": row["metric_value"],
            "label": row["metric_label"],
            "source": row["source"],
            "as_of": row["snapshot_date"],
        }

    return {"domains": summary, "generated_at": datetime.utcnow().isoformat()}


@router.get("/trend/{domain}/{metric_key}")
def get_metric_trend(
    domain: str,
    metric_key: str,
    days: int = Query(default=90, ge=7, le=365)
):
    """Returns historical trend data for a specific metric."""
    db = get_db()
    cursor = db.cursor()

    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT snapshot_date, metric_value, metric_label, source
        FROM metric_snapshots
        WHERE domain = ? AND metric_key = ? AND snapshot_date >= ?
        ORDER BY snapshot_date ASC
    """, (domain, metric_key, since))
    rows = cursor.fetchall()
    db.close()

    return {
        "domain": domain,
        "metric_key": metric_key,
        "days": days,
        "data": [
            {
                "date": r["snapshot_date"],
                "value": r["metric_value"],
                "label": r["metric_label"],
                "source": r["source"],
            }
            for r in rows
        ]
    }


@router.get("/domain/{domain}")
def get_domain_metrics(
    domain: str,
    days: int = Query(default=30, ge=1, le=365)
):
    """Returns all metrics for a specific security domain."""
    db = get_db()
    cursor = db.cursor()
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT metric_key, metric_value, metric_label, source, snapshot_date
        FROM metric_snapshots
        WHERE domain = ? AND snapshot_date >= ?
        ORDER BY snapshot_date DESC, metric_key
    """, (domain, since))
    rows = cursor.fetchall()
    db.close()

    return {
        "domain": domain,
        "metrics": [dict(r) for r in rows]
    }


@router.get("/kpis")
def get_kpis():
    """
    Returns computed KPIs with RAG (Red/Amber/Green) status for the dashboard.
    Thresholds are financial-services oriented.
    """
    db = get_db()
    cursor = db.cursor()

    def latest(domain, key):
        cursor.execute("""
            SELECT metric_value FROM metric_snapshots
            WHERE domain=? AND metric_key=?
            ORDER BY snapshot_date DESC LIMIT 1
        """, (domain, key))
        r = cursor.fetchone()
        return r["metric_value"] if r else None

    def rag(value, green_min=None, green_max=None, amber_min=None, amber_max=None, higher_is_better=True):
        if value is None:
            return "grey"
        if higher_is_better:
            if value >= (green_min or 0):
                return "green"
            elif value >= (amber_min or 0):
                return "amber"
            return "red"
        else:  # lower is better
            if value <= (green_max or 999999):
                return "green"
            elif value <= (amber_max or 999999):
                return "amber"
            return "red"

    kpis = [
        # Vulnerability Management
        {
            "id": "patch_compliance",
            "domain": "vulnerability_management",
            "label": "Patch Compliance",
            "metric_key": "patch_compliance_pct",
            "value": latest("vulnerability_management", "patch_compliance_pct"),
            "unit": "%",
            "rag": rag(latest("vulnerability_management", "patch_compliance_pct"), green_min=95, amber_min=85),
            "target": "95%",
            "description": "% of assets patched within SLA",
        },
        {
            "id": "critical_vuln_mttr",
            "domain": "vulnerability_management",
            "label": "Critical Vuln MTTR",
            "metric_key": "critical_vuln_mttr_days",
            "value": latest("vulnerability_management", "critical_vuln_mttr_days"),
            "unit": "days",
            "rag": rag(latest("vulnerability_management", "critical_vuln_mttr_days"), green_max=15, amber_max=30, higher_is_better=False),
            "target": "≤15 days",
            "description": "Mean time to remediate critical vulnerabilities",
        },
        {
            "id": "exposure_score",
            "domain": "vulnerability_management",
            "label": "Exposure Score",
            "metric_key": "exposure_score",
            "value": latest("vulnerability_management", "exposure_score"),
            "unit": "/100",
            "rag": rag(latest("vulnerability_management", "exposure_score"), green_max=30, amber_max=60, higher_is_better=False),
            "target": "<30",
            "description": "Microsoft Defender exposure score (lower is better)",
        },
        # Endpoint Protection
        {
            "id": "endpoint_coverage",
            "domain": "endpoint_protection",
            "label": "Endpoint Coverage",
            "metric_key": "endpoint_coverage_pct",
            "value": latest("endpoint_protection", "endpoint_coverage_pct"),
            "unit": "%",
            "rag": rag(latest("endpoint_protection", "endpoint_coverage_pct"), green_min=99, amber_min=95),
            "target": "99%",
            "description": "% of endpoints with active EDR agent",
        },
        # Identity & Access
        {
            "id": "mfa_enrollment",
            "domain": "identity_access",
            "label": "MFA Enrollment",
            "metric_key": "mfa_enrollment_pct",
            "value": latest("identity_access", "mfa_enrollment_pct"),
            "unit": "%",
            "rag": rag(latest("identity_access", "mfa_enrollment_pct"), green_min=98, amber_min=90),
            "target": "100%",
            "description": "% of users enrolled in MFA",
        },
        {
            "id": "orphan_accounts",
            "domain": "identity_access",
            "label": "Orphan Accounts",
            "metric_key": "orphan_account_pct",
            "value": latest("identity_access", "orphan_account_pct"),
            "unit": "%",
            "rag": rag(latest("identity_access", "orphan_account_pct"), green_max=1, amber_max=3, higher_is_better=False),
            "target": "<1%",
            "description": "Accounts inactive >90 days",
        },
        # Incident Response
        {
            "id": "mttd",
            "domain": "incident_response",
            "label": "MTTD",
            "metric_key": "mttd_hours",
            "value": latest("incident_response", "mttd_hours"),
            "unit": "hrs",
            "rag": rag(latest("incident_response", "mttd_hours"), green_max=4, amber_max=24, higher_is_better=False),
            "target": "≤4 hrs",
            "description": "Mean time to detect incidents",
        },
        {
            "id": "mttr",
            "domain": "incident_response",
            "label": "MTTR",
            "metric_key": "mttr_hours",
            "value": latest("incident_response", "mttr_hours"),
            "unit": "hrs",
            "rag": rag(latest("incident_response", "mttr_hours"), green_max=24, amber_max=72, higher_is_better=False),
            "target": "≤24 hrs",
            "description": "Mean time to resolve incidents",
        },
        # Phishing Awareness
        {
            "id": "phishing_click_rate",
            "domain": "phishing_awareness",
            "label": "Phishing Click Rate",
            "metric_key": "click_rate_pct",
            "value": latest("phishing_awareness", "click_rate_pct"),
            "unit": "%",
            "rag": rag(latest("phishing_awareness", "click_rate_pct"), green_max=3, amber_max=8, higher_is_better=False),
            "target": "<3%",
            "description": "% of users who clicked simulated phishing",
        },
        {
            "id": "training_completion",
            "domain": "phishing_awareness",
            "label": "Training Completion",
            "metric_key": "training_completion_pct",
            "value": latest("phishing_awareness", "training_completion_pct"),
            "unit": "%",
            "rag": rag(latest("phishing_awareness", "training_completion_pct"), green_min=95, amber_min=85),
            "target": "95%",
            "description": "% of employees who completed security training",
        },
        # Compliance
        {
            "id": "secure_score",
            "domain": "compliance",
            "label": "Secure Score",
            "metric_key": "secure_score_pct",
            "value": latest("compliance", "secure_score_pct"),
            "unit": "%",
            "rag": rag(latest("compliance", "secure_score_pct"), green_min=80, amber_min=65),
            "target": "≥80%",
            "description": "Microsoft Secure Score percentage",
        },
        {
            "id": "controls_coverage",
            "domain": "compliance",
            "label": "Controls Coverage",
            "metric_key": "controls_coverage_pct",
            "value": latest("compliance", "controls_coverage_pct"),
            "unit": "%",
            "rag": rag(latest("compliance", "controls_coverage_pct"), green_min=95, amber_min=85),
            "target": "95%",
            "description": "% of required controls implemented",
        },
    ]

    db.close()

    green = sum(1 for k in kpis if k["rag"] == "green")
    amber = sum(1 for k in kpis if k["rag"] == "amber")
    red = sum(1 for k in kpis if k["rag"] == "red")
    total_with_data = sum(1 for k in kpis if k["value"] is not None)

    return {
        "kpis": kpis,
        "summary": {
            "green": green,
            "amber": amber,
            "red": red,
            "grey": len(kpis) - total_with_data,
            "total": len(kpis),
            "overall_health": round((green / total_with_data * 100) if total_with_data > 0 else 0, 1),
        }
    }


@router.get("/sync-log")
def get_sync_log(limit: int = Query(default=50, le=200)):
    """Returns recent connector sync history."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT * FROM sync_log ORDER BY synced_at DESC LIMIT ?", (limit,)
    )
    rows = cursor.fetchall()
    db.close()
    return {"log": [dict(r) for r in rows]}
