from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Optional
import os
import shutil
from connectors import get_connector, get_all_connectors
from database import get_db

router = APIRouter()


@router.get("/status")
def get_connector_status():
    """Returns enabled/disabled status and last sync for all connectors."""
    db = get_db()
    cursor = db.cursor()
    connectors = get_all_connectors()
    result = {}

    for name, conn in connectors.items():
        cursor.execute("""
            SELECT status, message, records_synced, synced_at
            FROM sync_log WHERE connector = ?
            ORDER BY synced_at DESC LIMIT 1
        """, (name,))
        last = cursor.fetchone()

        result[name] = {
            "enabled": conn.is_enabled(),
            "last_sync": dict(last) if last else None,
        }

    db.close()
    return result


@router.post("/sync/{connector_name}")
def trigger_sync(connector_name: str):
    """Trigger a sync for a specific connector."""
    try:
        conn = get_connector(connector_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not conn.is_enabled() and connector_name != "spreadsheet":
        raise HTTPException(
            status_code=400,
            detail=f"Connector '{connector_name}' is not enabled. Check config.yaml."
        )

    try:
        result = conn.sync()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/sync/all")
def sync_all():
    """Trigger sync for all enabled connectors."""
    connectors = get_all_connectors()
    results = {}

    for name, conn in connectors.items():
        if conn.is_enabled() or name == "spreadsheet":
            try:
                results[name] = conn.sync()
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
        else:
            results[name] = {"status": "skipped", "reason": "not enabled"}

    return results


@router.post("/upload")
async def upload_spreadsheet(file: UploadFile = File(...)):
    """Upload a spreadsheet file for ingestion."""
    from connectors.spreadsheet import SpreadsheetConnector

    allowed_extensions = {".xlsx", ".xls", ".csv"}
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {allowed_extensions}"
        )

    conn = SpreadsheetConnector()
    upload_dir = conn.watch_dir
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, file.filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = conn.ingest_file(filepath)
        return result
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
