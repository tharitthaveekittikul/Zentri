from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.system_backup import SystemBackup
from app.services import system_backup as backup_service

router = APIRouter(prefix="/system", tags=["system"])
logger = get_logger(__name__)


@router.get("/export")
async def export_system(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    backup = await backup_service.export_backup(db, current_user)
    filename = f"zentri-backup-{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')}.json"
    return JSONResponse(
        content=backup.model_dump(mode="json"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", status_code=200)
async def import_system(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import json
    try:
        raw = await file.read()
        data = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    version = data.get("version", "")
    if version not in backup_service.SUPPORTED_VERSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported backup version: {version}")

    try:
        backup = SystemBackup.model_validate(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid backup format: {exc}")

    await backup_service.import_backup(db, current_user, backup)
    logger.info("System import completed for user=%s", current_user.id)
    return {"ok": True}
