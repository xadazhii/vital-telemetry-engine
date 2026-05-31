from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.db.session import get_db
from app.models.models import Alert, Physician
from app.schemas.schemas import AlertResponse
from app.core.security import get_current_physician

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/", response_model=List[AlertResponse])
async def list_alerts(
    patient_id: int | None = Query(None, description="Filter by patient"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: Physician = Depends(get_current_physician),
):
    q = select(Alert).order_by(Alert.created_at.desc())
    if patient_id is not None:
        q = q.where(Alert.patient_id == patient_id)
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    return result.scalars().all()
