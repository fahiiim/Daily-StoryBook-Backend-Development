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

`POST /coach/nutrition-plans` assigns nutrition targets, exercise instructions, and daily goals to
an accepted client. SELF users record their own meals through the routine meal-log APIs.

```json
{
  "client_id": "f53157d5fe4949fcacc463cfe7f0dee3",
  "daily_calories": 5000,
  "protein": 1000,
  "carbs": 1000,
  "fat": 1000,
  "fiber": 1000,
  "water_goal": 1000,
  "workout_plan": [
    "pushup"
  ],
  "daily_goals": [
    "string"
  ],
  "notes": "string",
  "date": "2026-07-20"
}
```

`workout_plan` and `daily_goals` are ordered arrays with no application-level item-count limit.
Coach and client nutrition-plan GET responses, routine dashboards, storybook context, and weekly
summary context expose the same assigned values.
