from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.db.session import get_db
from app.models.models import Alert
from app.schemas.schemas import AlertResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.get("/", response_model=List[AlertResponse])
async def list_alerts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).order_by(Alert.created_at.desc()))
    return result.scalars().all()
