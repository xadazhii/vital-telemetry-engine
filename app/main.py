from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api import patients, telemetry, alerts
from app.db.session import engine, Base
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

@app.on_event("startup")
async def startup():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.include_router(patients.router)
app.include_router(telemetry.router)
app.include_router(alerts.router)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/dashboard")
async def dashboard():
    return FileResponse("app/static/index.html")

@app.get("/")
async def root():
    return {"message": "Cardio Monitoring API is running"}
