"""
Microsoft Defender for Endpoint connector.
Uses Microsoft Graph API / Defender API with OAuth2 client credentials flow.

Required config.yaml fields:
  connectors:
    microsoft_defender:
      tenant_id: "your-tenant-id"
      client_id: "your-app-client-id"
      client_secret: "your-client-secret"
      enabled: true
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List
from config_loader import get_connector_config
from database import get_db


class MicrosoftDefenderConnector:
    NAME = "microsoft_defender"
    BASE_URL = "https://api.securitycenter.microsoft.com/api"
    GRAPH_URL = "https://graph.microsoft.com/v1.0"
    TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    def __init__(self):
        self.config = get_connector_config(self.NAME)
        self._token = None
        self._token_expiry = None

    def is_enabled(self) -> bool:
        return self.config.get("enabled", False)

    def _get_token(self) -> str:
        if self._token and self._token_expiry and datetime.utcnow() < self._token_expiry:
            return self._token

        url = self.TOKEN_URL.format(tenant_id=self.config["tenant_id"])
        resp = requests.post(url, data={
            "grant_type": "client_credentials",
            "client_id": self.config["client_id"],
            "client_secret": self.config["client_secret"],
            "scope": "https://api.securitycenter.microsoft.com/.default"
        })
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = datetime.utcnow() + timedelta(seconds=data["expires_in"] - 60)
        return self._token

    def _get(self, endpoint: str, base: str = None) -> Dict:
        token = self._get_token()
        url = f"{base or self.BASE_URL}/{endpoint}"
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        return resp.json()

    def fetch_endpoint_coverage(self) -> Dict[str, Any]:
        """Get total onboarded machines vs expected coverage."""
        data = self._get("machines?$count=true&$top=1")
        total_onboarded = data.get("@odata.count", 0)

        # Active / healthy machines
        active = self._get("machines?$filter=healthStatus eq 'Active'&$count=true&$top=1")
        active_count = active.get("@odata.count", 0)

        coverage_pct = (active_count / total_onboarded * 100) if total_onboarded > 0 else 0

        return {
            "total_onboarded": total_onboarded,
            "active_endpoints": active_count,
            "coverage_percent": round(coverage_pct, 1),
        }

    def fetch_vulnerability_stats(self) -> Dict[str, Any]:
        """Fetch vulnerability exposure stats."""
        stats = self._get("vulnerabilities/machinesVulnerabilitiesCount")
        exposure = self._get("exposureScore")

        return {
            "exposure_score": exposure.get("score", 0),
            "exposure_level": exposure.get("exposureLevel", "Unknown"),
            "total_vulnerabilities": stats.get("@odata.count", 0),
        }

    def fetch_active_alerts(self) -> List[Dict]:
        """Fetch active security alerts."""
        data = self._get("alerts?$filter=status ne 'Resolved'&$top=100&$orderby=severity desc")
        alerts = data.get("value", [])

        severity_counts = {"High": 0, "Medium": 0, "Low": 0, "Informational": 0}
        for alert in alerts:
            sev = alert.get("severity", "Informational")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "total_active_alerts": len(alerts),
            "by_severity": severity_counts,
            "alerts": [
                {
                    "id": a.get("id"),
                    "title": a.get("title"),
                    "severity": a.get("severity"),
                    "status": a.get("status"),
                    "created_at": a.get("alertCreationTime"),
                }
                for a in alerts[:20]
            ]
        }

    def fetch_secure_score(self) -> Dict[str, Any]:
        """Fetch Microsoft Secure Score via Graph API."""
        token = self._get_token()
        resp = requests.get(
            f"{self.GRAPH_URL}/security/secureScores?$top=1",
            headers={"Authorization": f"Bearer {token}"}
        )
        resp.raise_for_status()
        scores = resp.json().get("value", [{}])
        score = scores[0] if scores else {}
        return {
            "current_score": score.get("currentScore", 0),
            "max_score": score.get("maxScore", 0),
            "percent": round(score.get("currentScore", 0) / score.get("maxScore", 1) * 100, 1),
        }

    def sync(self) -> Dict[str, Any]:
        """Run full sync and write metrics to DB."""
        db = get_db()
        cursor = db.cursor()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        records = 0

        try:
            # Endpoint coverage
            ep = self.fetch_endpoint_coverage()
            for key, val in [
                ("endpoint_coverage_pct", ep["coverage_percent"]),
                ("total_endpoints", ep["total_onboarded"]),
                ("active_endpoints", ep["active_endpoints"]),
            ]:
                cursor.execute(
                    "INSERT INTO metric_snapshots (domain, metric_key, metric_value, source, snapshot_date) VALUES (?,?,?,?,?)",
                    ("endpoint_protection", key, val, self.NAME, today)
                )
                records += 1

            # Vulnerability stats
            vuln = self.fetch_vulnerability_stats()
            cursor.execute(
                "INSERT INTO metric_snapshots (domain, metric_key, metric_value, metric_label, source, snapshot_date) VALUES (?,?,?,?,?,?)",
                ("vulnerability_management", "exposure_score", vuln["exposure_score"], vuln["exposure_level"], self.NAME, today)
            )
            records += 1

            # Secure score
            sec = self.fetch_secure_score()
            cursor.execute(
                "INSERT INTO metric_snapshots (domain, metric_key, metric_value, source, snapshot_date) VALUES (?,?,?,?,?)",
                ("compliance", "secure_score_pct", sec["percent"], self.NAME, today)
            )
            records += 1

            db.commit()
            cursor.execute(
                "INSERT INTO sync_log (connector, status, message, records_synced) VALUES (?,?,?,?)",
                (self.NAME, "success", "Sync completed successfully", records)
            )
            db.commit()
            return {"status": "success", "records_synced": records}

        except Exception as e:
            db.rollback()
            cursor.execute(
                "INSERT INTO sync_log (connector, status, message) VALUES (?,?,?)",
                (self.NAME, "error", str(e))
            )
            db.commit()
            raise
        finally:
            db.close()
