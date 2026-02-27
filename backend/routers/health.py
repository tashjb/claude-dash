from fastapi import APIRouter
from datetime import datetime
from database import get_db

router = APIRouter()

@router.get("")
def health_check():
    try:
        db = get_db()
        db.execute("SELECT 1")
        db.close()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "ok",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat(),
    }
