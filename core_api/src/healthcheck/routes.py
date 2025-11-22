from fastapi import APIRouter
from fastapi.responses import JSONResponse
from .service import get_health_status

router = APIRouter()


@router.get("/", tags=["Health"])
async def health_check():
    return JSONResponse(content=get_health_status())
