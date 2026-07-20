# DailyStoryBook Backend (FastAPI)

Production-ready, modular FastAPI starter using Python 3.12, SQLAlchemy 2.0, Alembic, PostgreSQL, and Pydantic v2.

## Tech Stack

- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL (psycopg)
- Pydantic v2 + pydantic-settings
- Uvicorn
- python-dotenv
- httpx
- passlib[bcrypt]
- python-jose
- structlog

## Project Structure

```text
app/
  api/
  core/
  db/
  models/
  schemas/
  services/
  repositories/
  utils/
  middleware/
  dependencies/
  routers/
tests/
alembic/
```

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -e .
pip install -e .[dev]
```

3. Update `.env` for your environment.
4. Run the app:

```bash
uvicorn app.main:app --reload
```

5. Health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"healthy"}
```

## Alembic

Create a migration:

```bash
alembic revision --autogenerate -m "init"
```

Apply migrations:

```bash
alembic upgrade head
```

## Coach daily plan API

`POST /coach/nutrition-plans` creates one plan per coach/client/date combination. Meal names and
meal contents are not coach-authored fields; SELF users record those through the routine meal-log
APIs. A coach plan accepts nutrition targets, an ordered workout instruction list, and an ordered
daily-goal list:

```json
{
  "client_id": "00000000-0000-0000-0000-000000000000",
  "date": "2026-07-20",
  "daily_calories": 2100,
  "protein": 150,
  "carbs": 230,
  "fat": 60,
  "fiber": 28,
  "water_goal": 3.2,
  "workout_plan": [
    "Do 30 pushups",
    "Walk for 20 minutes"
  ],
  "daily_goals": [
    "Drink 3.2 litres of water",
    "Sleep for 8 hours"
  ],
  "notes": "Week 1"
}
```

Neither `workout_plan` nor `daily_goals` has an application-level item-count limit. The standalone
workout-plan APIs likewise use an ordered `exercises` array. `PUT` requires and replaces these
arrays, and an empty array clears them.
