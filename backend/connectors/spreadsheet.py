"""
Spreadsheet connector — ingests metrics from Excel (.xlsx) or CSV files.
Supports a standardized template format as well as flexible column mapping.

Drop files into the configured watch_directory and call /api/connectors/spreadsheet/sync.

Expected template columns (case-insensitive):
  domain, metric_key, metric_value, metric_label (optional), snapshot_date (optional), source (optional)

Supported domains: vulnerability_management, endpoint_protection,
                   identity_access, incident_response, phishing_awareness,
                   compliance

Example rows:
  vulnerability_management | critical_vulns_open | 47 | Critical | 2024-01-15
  phishing_awareness       | click_rate_pct      | 4.2 |          | 2024-01-15
"""

import os
import glob
from datetime import datetime
from typing import Dict, Any, List

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from config_loader import get_connector_config
from database import get_db


VALID_DOMAINS = {
    "vulnerability_management",
    "endpoint_protection",
    "identity_access",
    "incident_response",
    "phishing_awareness",
    "compliance",
}

COLUMN_ALIASES = {
    "domain": ["domain", "area", "category"],
    "metric_key": ["metric_key", "metric", "key", "name", "kpi"],
    "metric_value": ["metric_value", "value", "result", "score", "count"],
    "metric_label": ["metric_label", "label", "status", "rating"],
    "snapshot_date": ["snapshot_date", "date", "report_date", "as_of"],
    "source": ["source", "tool", "system"],
}


def _resolve_columns(df_columns: List[str]) -> Dict[str, str]:
    """Map standardized field names to actual DataFrame column names."""
    lower_cols = {c.lower().strip(): c for c in df_columns}
    resolved = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower_cols:
                resolved[field] = lower_cols[alias]
                break
    return resolved


class SpreadsheetConnector:
    NAME = "spreadsheet"

    def __init__(self):
        self.config = get_connector_config(self.NAME)
        self.watch_dir = self.config.get("watch_directory", "./data/uploads")

    def is_enabled(self) -> bool:
        return True  # Always enabled

    def _load_file(self, filepath: str) -> "pd.DataFrame":
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas and openpyxl are required. Run: pip install pandas openpyxl")

        ext = os.path.splitext(filepath)[1].lower()
        if ext in (".xlsx", ".xls"):
            return pd.read_excel(filepath)
        elif ext == ".csv":
            return pd.read_csv(filepath)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def _process_dataframe(self, df: "pd.DataFrame", filepath: str) -> List[Dict]:
        """Normalize a DataFrame into a list of metric records."""
        col_map = _resolve_columns(list(df.columns))

        required = {"domain", "metric_key", "metric_value"}
        missing = required - set(col_map.keys())
        if missing:
            raise ValueError(
                f"File '{os.path.basename(filepath)}' is missing required columns: {missing}. "
                f"Found: {list(df.columns)}"
            )

        today = datetime.utcnow().strftime("%Y-%m-%d")
        records = []

        for _, row in df.iterrows():
            domain = str(row[col_map["domain"]]).strip().lower().replace(" ", "_")
            if domain not in VALID_DOMAINS:
                print(f"  Skipping unknown domain: '{domain}'")
                continue

            try:
                value = float(row[col_map["metric_value"]])
            except (ValueError, TypeError):
                print(f"  Skipping non-numeric value for {domain}/{row[col_map['metric_key']]}")
                continue

            record = {
                "domain": domain,
                "metric_key": str(row[col_map["metric_key"]]).strip().lower().replace(" ", "_"),
                "metric_value": value,
                "metric_label": str(row[col_map.get("metric_label", "")]).strip() if "metric_label" in col_map else None,
                "snapshot_date": str(row[col_map["snapshot_date"]]).strip()[:10] if "snapshot_date" in col_map else today,
                "source": str(row[col_map.get("source", "")]).strip() if "source" in col_map else f"spreadsheet:{os.path.basename(filepath)}",
            }
            records.append(record)

        return records

    def ingest_file(self, filepath: str) -> Dict[str, Any]:
        """Ingest a single file and write to DB."""
        db = get_db()
        cursor = db.cursor()
        records_written = 0

        try:
            df = self._load_file(filepath)
            records = self._process_dataframe(df, filepath)

            for r in records:
                cursor.execute(
                    """INSERT INTO metric_snapshots 
                       (domain, metric_key, metric_value, metric_label, source, snapshot_date)
                       VALUES (?,?,?,?,?,?)""",
                    (r["domain"], r["metric_key"], r["metric_value"],
                     r["metric_label"], r["source"], r["snapshot_date"])
                )
                records_written += 1

            db.commit()
            cursor.execute(
                "INSERT INTO sync_log (connector, status, message, records_synced) VALUES (?,?,?,?)",
                (self.NAME, "success", f"Ingested: {os.path.basename(filepath)}", records_written)
            )
            db.commit()
            return {
                "status": "success",
                "file": os.path.basename(filepath),
                "records_ingested": records_written,
            }

        except Exception as e:
            db.rollback()
            cursor.execute(
                "INSERT INTO sync_log (connector, status, message) VALUES (?,?,?)",
                (self.NAME, "error", f"{os.path.basename(filepath)}: {str(e)}")
            )
            db.commit()
            raise
        finally:
            db.close()

    def sync(self) -> Dict[str, Any]:
        """Ingest all files in the watch directory."""
        os.makedirs(self.watch_dir, exist_ok=True)
        patterns = ["*.xlsx", "*.xls", "*.csv"]
        files = []
        for p in patterns:
            files.extend(glob.glob(os.path.join(self.watch_dir, p)))

        if not files:
            return {"status": "success", "message": f"No files found in {self.watch_dir}", "files_processed": 0}

        results = []
        total_records = 0
        for filepath in files:
            try:
                result = self.ingest_file(filepath)
                total_records += result["records_ingested"]
                results.append(result)
            except Exception as e:
                results.append({"status": "error", "file": os.path.basename(filepath), "error": str(e)})

        return {
            "status": "success",
            "files_processed": len(files),
            "total_records_ingested": total_records,
            "results": results,
        }
