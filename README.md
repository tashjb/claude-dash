# SecureMetrics Dashboard

A locally-hosted security program metrics dashboard for financial services.
Connects to Microsoft Defender, Okta, and Excel/CSV spreadsheets to track
KPIs across six security domains with RAG (Red/Amber/Green) status indicators.

---

## Quick Start

### Option A — Docker (recommended, one command)

```bash
# 1. Clone/unzip the project
cd security-dashboard

# 2. Edit config.yaml with your API credentials (see Configuration section)
cp config.yaml config.yaml   # it's already there

# 3. Start everything
docker compose up --build

# Dashboard: http://localhost:3000
# API docs:  http://localhost:8000/docs
```

### Option B — Run locally without Docker

**Backend (Python 3.10+)**
```bash
cd backend
pip install -r requirements.txt
python main.py
# Runs on http://localhost:8000
```

**Frontend (Node 18+)**
```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:3000
```

---

## Configuration

Edit `config.yaml` to enable connectors. **Never commit this file** — add it to `.gitignore`.

### Microsoft Defender for Endpoint

1. Go to **Azure Portal → App Registrations → New registration**
2. Add API permissions: `SecurityAlert.Read.All`, `Machine.Read.All`,
   `Vulnerability.Read.All`, `SecureScore.Read.All` (all Application type)
3. Grant admin consent
4. Create a client secret

```yaml
connectors:
  microsoft_defender:
    enabled: true
    tenant_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    client_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    client_secret: "your-secret-here"
```

### Okta

1. Go to **Okta Admin → Security → API → Tokens → Create Token**
2. The token needs Read access to Users and Factors

```yaml
connectors:
  okta:
    enabled: true
    domain: "yourorg.okta.com"
    api_token: "your-okta-api-token"
```

### Spreadsheets (Excel / CSV)

No configuration required. Either:
- **Upload via UI**: Go to the Upload tab in the dashboard and drag-and-drop a file
- **Drop files**: Place `.xlsx` or `.csv` files in `./data/uploads/` and trigger a sync

**Required columns:** `domain`, `metric_key`, `metric_value`

**Valid domains:**

| Domain | Description |
|--------|-------------|
| `vulnerability_management` | Patch rates, MTTR, open vulnerabilities |
| `endpoint_protection` | EDR coverage, agent health |
| `identity_access` | MFA, orphan accounts, admin ratios |
| `incident_response` | MTTD, MTTR, open incidents |
| `phishing_awareness` | Click rates, training completion |
| `compliance` | Controls coverage, audit findings |

Download the CSV template from the Upload tab in the dashboard.

---

## Metrics & Targets

| KPI | Target | Green | Amber | Red |
|-----|--------|-------|-------|-----|
| Patch Compliance | 95% | ≥95% | ≥85% | <85% |
| Critical Vuln MTTR | ≤15 days | ≤15d | ≤30d | >30d |
| Exposure Score | <30 | <30 | <60 | ≥60 |
| Endpoint Coverage | 99% | ≥99% | ≥95% | <95% |
| MFA Enrollment | 100% | ≥98% | ≥90% | <90% |
| Orphan Accounts | <1% | <1% | <3% | ≥3% |
| MTTD | ≤4 hrs | ≤4h | ≤24h | >24h |
| MTTR | ≤24 hrs | ≤24h | ≤72h | >72h |
| Phishing Click Rate | <3% | <3% | <8% | ≥8% |
| Training Completion | 95% | ≥95% | ≥85% | <85% |
| Secure Score | ≥80% | ≥80% | ≥65% | <65% |
| Controls Coverage | 95% | ≥95% | ≥85% | <85% |

Thresholds are tunable in `backend/routers/metrics.py` → `get_kpis()`.

---

## Adding a New Connector

1. Create `backend/connectors/your_tool.py`:
```python
class YourToolConnector:
    NAME = "your_tool"

    def __init__(self):
        self.config = get_connector_config(self.NAME)

    def is_enabled(self):
        return self.config.get("enabled", False)

    def sync(self):
        # Fetch data, write to metric_snapshots table
        # Return {"status": "success", "records_synced": N}
        pass
```

2. Register it in `backend/connectors/__init__.py`:
```python
from connectors.your_tool import YourToolConnector
CONNECTOR_REGISTRY["your_tool"] = YourToolConnector
```

3. Add credentials to `config.yaml`

4. Restart the backend — it appears in the Connectors tab automatically.

**Common connectors to add next:** Qualys, Tenable, CrowdStrike, ServiceNow, KnowBe4, Proofpoint

---

## Project Structure

```
security-dashboard/
├── config.yaml                 # API credentials (do not commit)
├── docker-compose.yml
├── data/
│   ├── metrics.db              # SQLite database (auto-created)
│   └── uploads/                # Drop spreadsheets here
├── backend/
│   ├── main.py                 # FastAPI app
│   ├── database.py             # DB schema & helpers
│   ├── config_loader.py        # config.yaml loader
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── connectors/
│   │   ├── __init__.py         # Registry
│   │   ├── microsoft_defender.py
│   │   ├── okta.py
│   │   └── spreadsheet.py
│   └── routers/
│       ├── metrics.py          # KPIs, trends, summaries
│       ├── connectors.py       # Sync triggers, file upload
│       └── health.py
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── App.jsx             # Main dashboard
        ├── index.css
        └── components/
            ├── KPICard.jsx
            ├── TrendChart.jsx
            ├── ConnectorStatus.jsx
            ├── UploadPanel.jsx
            └── SyncLog.jsx
```

---

## API Reference

Interactive docs available at `http://localhost:8000/docs` (Swagger UI).

| Endpoint | Description |
|----------|-------------|
| `GET /api/metrics/kpis` | All KPIs with RAG status |
| `GET /api/metrics/summary` | Latest value per metric per domain |
| `GET /api/metrics/trend/{domain}/{key}` | 90-day trend for a metric |
| `GET /api/connectors/status` | Connector enabled/last sync status |
| `POST /api/connectors/sync/{name}` | Trigger sync for one connector |
| `POST /api/connectors/sync/all` | Trigger sync for all connectors |
| `POST /api/connectors/upload` | Upload a spreadsheet file |
| `GET /api/metrics/sync-log` | Sync history |

---

## Security Notes

- The dashboard is **not** authenticated by default (local use only)
- Do not expose port 8000 or 3000 to the public internet
- Store `config.yaml` securely; consider using a secrets manager for production
- The SQLite database at `./data/metrics.db` contains your security metrics
- Add `config.yaml` and `data/` to `.gitignore`
