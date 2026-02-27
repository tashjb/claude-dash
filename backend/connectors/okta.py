"""
Okta connector for Identity & Access Management metrics.
Uses Okta REST API with API token authentication.

Required config.yaml fields:
  connectors:
    okta:
      domain: "yourorg.okta.com"
      api_token: "your-okta-api-token"
      enabled: true
      # Optional: expected total user count if not fully in Okta
      expected_user_count: 0
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List
from config_loader import get_connector_config
from database import get_db


class OktaConnector:
    NAME = "okta"

    def __init__(self):
        self.config = get_connector_config(self.NAME)
        domain = self.config.get("domain", "")
        self.base_url = f"https://{domain}/api/v1"
        self.headers = {
            "Authorization": f"SSWS {self.config.get('api_token', '')}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def is_enabled(self) -> bool:
        return self.config.get("enabled", False)

    def _get(self, path: str, params: Dict = None) -> Any:
        resp = requests.get(f"{self.base_url}/{path}", headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json()

    def _get_all_pages(self, path: str, params: Dict = None) -> List[Dict]:
        """Follow Okta pagination links to get all results."""
        url = f"{self.base_url}/{path}"
        results = []
        while url:
            resp = requests.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            results.extend(resp.json())
            # Okta uses Link headers for pagination
            links = resp.headers.get("Link", "")
            url = None
            params = None  # params only on first request
            for link in links.split(","):
                if 'rel="next"' in link:
                    url = link.split(";")[0].strip().strip("<>")
                    break
        return results

    def fetch_user_stats(self) -> Dict[str, Any]:
        """Get active users, deprovisioned, and locked out."""
        active = self._get("users", {"filter": 'status eq "ACTIVE"', "limit": 1})
        # Use count from a limit=1 call — Okta doesn't return total count in body
        # so we paginate to count
        active_users = self._get_all_pages("users", {"filter": 'status eq "ACTIVE"'})
        deprovisioned = self._get_all_pages("users", {"filter": 'status eq "DEPROVISIONED"'})
        locked = self._get_all_pages("users", {"filter": 'status eq "LOCKED_OUT"'})
        suspended = self._get_all_pages("users", {"filter": 'status eq "SUSPENDED"'})

        return {
            "active_users": len(active_users),
            "deprovisioned_users": len(deprovisioned),
            "locked_out_users": len(locked),
            "suspended_users": len(suspended),
        }

    def fetch_mfa_enrollment(self) -> Dict[str, Any]:
        """
        Estimate MFA enrollment rate.
        Counts users enrolled in any MFA factor vs total active users.
        """
        # Get all active users
        active_users = self._get_all_pages("users", {"filter": 'status eq "ACTIVE"'})
        total = len(active_users)

        mfa_enrolled = 0
        for user in active_users:
            uid = user["id"]
            try:
                factors = self._get(f"users/{uid}/factors")
                if factors:
                    mfa_enrolled += 1
            except Exception:
                pass  # Skip users where factor fetch fails

        pct = round(mfa_enrolled / total * 100, 1) if total > 0 else 0
        return {
            "total_active_users": total,
            "mfa_enrolled": mfa_enrolled,
            "mfa_enrollment_pct": pct,
            "not_enrolled": total - mfa_enrolled,
        }

    def fetch_orphan_accounts(self, days_inactive: int = 90) -> Dict[str, Any]:
        """
        Find accounts that haven't logged in for N days (potential orphans).
        """
        cutoff = (datetime.utcnow() - timedelta(days=days_inactive)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        stale_filter = f'status eq "ACTIVE" and lastLogin lt "{cutoff}"'
        stale_users = self._get_all_pages("users", {"filter": stale_filter})

        active_users = self._get_all_pages("users", {"filter": 'status eq "ACTIVE"'})
        total_active = len(active_users)

        orphan_pct = round(len(stale_users) / total_active * 100, 1) if total_active > 0 else 0

        return {
            "total_active_users": total_active,
            "stale_accounts": len(stale_users),
            "stale_threshold_days": days_inactive,
            "orphan_account_pct": orphan_pct,
        }

    def fetch_admin_accounts(self) -> Dict[str, Any]:
        """Count privileged/admin accounts."""
        admins = self._get_all_pages("users", {
            "filter": 'status eq "ACTIVE"',
            "search": 'profile.isAdmin eq true'
        })
        active_users = self._get_all_pages("users", {"filter": 'status eq "ACTIVE"'})
        total = len(active_users)
        admin_count = len(admins)

        return {
            "admin_count": admin_count,
            "total_users": total,
            "admin_pct": round(admin_count / total * 100, 1) if total > 0 else 0,
        }

    def sync(self) -> Dict[str, Any]:
        """Run full sync and write metrics to DB."""
        db = get_db()
        cursor = db.cursor()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        records = 0

        try:
            # User stats
            users = self.fetch_user_stats()
            for key, val in [
                ("active_users", users["active_users"]),
                ("deprovisioned_users", users["deprovisioned_users"]),
                ("locked_out_users", users["locked_out_users"]),
            ]:
                cursor.execute(
                    "INSERT INTO metric_snapshots (domain, metric_key, metric_value, source, snapshot_date) VALUES (?,?,?,?,?)",
                    ("identity_access", key, val, self.NAME, today)
                )
                records += 1

            # MFA enrollment
            mfa = self.fetch_mfa_enrollment()
            for key, val in [
                ("mfa_enrollment_pct", mfa["mfa_enrollment_pct"]),
                ("mfa_enrolled_count", mfa["mfa_enrolled"]),
                ("mfa_not_enrolled", mfa["not_enrolled"]),
            ]:
                cursor.execute(
                    "INSERT INTO metric_snapshots (domain, metric_key, metric_value, source, snapshot_date) VALUES (?,?,?,?,?)",
                    ("identity_access", key, val, self.NAME, today)
                )
                records += 1

            # Orphan accounts
            orphans = self.fetch_orphan_accounts()
            cursor.execute(
                "INSERT INTO metric_snapshots (domain, metric_key, metric_value, source, snapshot_date) VALUES (?,?,?,?,?)",
                ("identity_access", "orphan_account_pct", orphans["orphan_account_pct"], self.NAME, today)
            )
            records += 1

            db.commit()
            cursor.execute(
                "INSERT INTO sync_log (connector, status, message, records_synced) VALUES (?,?,?,?)",
                (self.NAME, "success", "Sync completed", records)
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
