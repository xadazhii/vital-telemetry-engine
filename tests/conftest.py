import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.db.session import Base, get_db
from app.core.security import get_current_physician
from app.main import app
from app.models.models import Patient, Telemetry, Alert, MedicalInsight, Physician

DATABASE_URL = "sqlite+aiosqlite:///test_db.sqlite"

engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)

TestingSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="function")
async def db():
    if os.path.exists("test_db.sqlite"):
        try:
            os.remove("test_db.sqlite")
        except Exception:
            pass

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

    if os.path.exists("test_db.sqlite"):
        try:
            os.remove("test_db.sqlite")
        except Exception:
            pass


@pytest_asyncio.fixture(scope="function")
async def client(db):
    async def override_get_db():
        async with TestingSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    mock_physician = Physician(id=1, name="Test Doctor", email="test@test.com")

    async def override_auth():
        return mock_physician

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_physician] = override_auth
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
