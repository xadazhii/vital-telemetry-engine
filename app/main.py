import logfire
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api import patients, telemetry, alerts, physicians, auth
from app.db.session import engine
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME, version="1.0.0")

# ── Logfire / OpenTelemetry instrumentation ────────────────────────────────
# In production: set LOGFIRE_TOKEN env var to enable cloud tracing.
# Falls back gracefully when OTel packages are not fully installed.
try:
    logfire.configure(send_to_logfire="if-token-present")
    logfire.instrument_fastapi(app)
    logfire.instrument_sqlalchemy(engine.sync_engine)
except Exception:
    pass

# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(physicians.router)
app.include_router(telemetry.router)
app.include_router(alerts.router)

# ── Static / Dashboard ─────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/dashboard")
async def dashboard():
    return FileResponse("app/static/index.html")


@app.get("/")
async def root():
    return {"message": "Cardio Monitoring API is running"}


@app.get("/health")
async def health():
    return {"status": "ok"}
