from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.services.hardware import detect_hardware

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/hardware")
async def hardware_info(_: User = Depends(get_current_user)):
    info = detect_hardware()
    return {
        "cpu_brand": info.cpu_brand,
        "ram_gb": round(info.ram_gb, 1),
        "is_apple_silicon": info.is_apple_silicon,
        "recommendation": info.recommendation,
    }
