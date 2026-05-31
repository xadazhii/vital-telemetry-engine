from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.db.session import get_db
from app.models.models import Physician
from app.schemas.schemas import PhysicianCreate, PhysicianResponse
from app.core.security import hash_password

router = APIRouter(prefix="/physicians", tags=["physicians"])


@router.post("/", response_model=PhysicianResponse, status_code=201)
async def create_physician(data: PhysicianCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Physician).where(Physician.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    physician = Physician(
        name=data.name,
        specialty=data.specialty,
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(physician)
    await db.commit()
    await db.refresh(physician)
    return physician


@router.get("/", response_model=List[PhysicianResponse])
async def list_physicians(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Physician).limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/{physician_id}", response_model=PhysicianResponse)
async def get_physician(physician_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Physician).where(Physician.id == physician_id))
    physician = result.scalar_one_or_none()
    if not physician:
        raise HTTPException(status_code=404, detail="Physician not found")
    return physician


@router.delete("/{physician_id}")
async def delete_physician(physician_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Physician).where(Physician.id == physician_id))
    physician = result.scalar_one_or_none()
    if not physician:
        raise HTTPException(status_code=404, detail="Physician not found")
    await db.delete(physician)
    await db.commit()
    return {"message": "Physician deleted"}
