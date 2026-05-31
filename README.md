# Cardio Live — Vital Telemetry Engine

A full-stack cardiac monitoring system built for real-time health data collection, signal analysis, and physician oversight. Connects Apple Watch health data to a live physician dashboard via a high-performance asynchronous backend.

## Screenshots

| iOS Companion App | Physician Dashboard |
|:-:|:-:|
| ![iOS App](docs/screenshots/ios_app.png) | ![Dashboard](docs/screenshots/dashboard.png) |

## Overview

**Cardio Live** bridges wearable health data with clinical workflows. The iOS app reads metrics directly from Apple HealthKit (heart rate, HRV, blood pressure, body composition) and auto-syncs them to the backend whenever new data is recorded. Physicians log in to a real-time web dashboard that surfaces clinical findings, alerts, and 7-day trends.

## Architecture

```
Apple Watch → HealthKit → iOS App (Swift)
                               │
                               ▼ HTTP / auto-sync
                        FastAPI Backend
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
         PostgreSQL          Redis           Celery
         (storage)        (pub/sub)        (analysis)
                               │
                               ▼ WebSocket
                      Physician Dashboard
```

## Tech Stack

### Backend
- **FastAPI** — async REST API + WebSocket
- **PostgreSQL** + **SQLAlchemy** (async) — data persistence
- **Celery** + **Redis** — background signal processing
- **Alembic** — database migrations
- **NumPy** — HRV / signal analysis (RMSSD, SDNN, pNN50, SNR)
- **Logfire** / **OpenTelemetry** — observability
- **JWT** (python-jose) — physician authentication
- **Docker Compose** — local infrastructure

### iOS (`ios/`)
- **Swift** + **SwiftUI**
- **HealthKit** — heart rate, HRV (SDNN), blood pressure, SpO2, height, weight, age
- **CoreLocation** + **Open-Meteo API** — real-time air quality (AQI, PM2.5)
- **HKObserverQuery** — background auto-sync on new data
- **WatchConnectivity** — Apple Watch support

### Dashboard
- Vanilla JS + Chart.js
- Real-time updates via WebSocket + Redis Pub/Sub
- JWT session management

## Features

- **Real-time monitoring** — live heart rate, blood pressure, HRV, SpO2, air quality
- **Clinical Summary** — auto-generated actionable findings (hypertension, bradycardia, elevated stress, underweight)
- **Signal analysis** — RMSSD, SDNN, pNN50, SNR calculated from 10-sample sliding window
- **7-day history import** — bulk import of Apple Watch heart rate history
- **Auto-sync** — HealthKit Observer triggers background sync on every new measurement
- **Physician auth** — JWT login, protected endpoints
- **Alerts** — anomaly detection for tachycardia, bradycardia, hypertension, hypotension, low SpO2
- **Air quality** — ambient AQI integrated into clinical context

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Xcode 15+ (for iOS app)

### Backend

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Start infrastructure
docker compose up -d

# 3. Run migrations
alembic upgrade head

# 4. Start API
uvicorn app.main:app --reload

# 5. Start worker
celery -A app.workers.celery_app worker --pool=solo --loglevel=info
```

Dashboard: `http://localhost:8000/dashboard`  
API docs: `http://localhost:8000/docs`

### iOS App

Open `ios/CardioWatch.xcodeproj` in Xcode, select your iPhone as target, and run (`⌘R`).

Enter your server IP in the app settings and tap **Sync Now**.

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/token` | — | Physician login |
| `GET` | `/patients/` | ✓ | List patients |
| `GET` | `/physicians/` | ✓ | List physicians |
| `POST` | `/telemetry/apple-health` | — | Apple Health sync |
| `POST` | `/telemetry/history-import` | — | Bulk HR history import |
| `GET` | `/telemetry/{id}` | ✓ | Patient telemetry |
| `GET` | `/telemetry/insights/{id}` | ✓ | Latest HRV insight |
| `GET` | `/alerts/` | ✓ | Alerts (filterable) |
| `WS` | `/telemetry/ws/{id}` | — | Live WebSocket feed |

## Environment Variables

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/cardio_db
REDIS_URL=redis://localhost:6379/0
LOGFIRE_TOKEN=          # optional — enables cloud tracing
```

## Running Tests

```bash
pytest tests/ -v
```

14 tests covering API endpoints, signal analysis algorithms, and background task logic.
