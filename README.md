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
an accepted client for seven calendar days. The supplied `date` is the first valid day, and the
assignment remains active through `date + 6 days`. SELF users record their own meals through the
routine meal-log APIs.

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
summary context expose the same assigned values. Responses include `valid_from`, `valid_until`, and
`validity_days`. Overlapping seven-day plans for the same coach/client are rejected. Historical
overlaps created before this rule are retained without data loss; the newest active assignment is
used for routine/dashboard targets.

## Assigned workout progress API

Standalone workout-plan CRUD and assignment APIs were removed. Coaches assign exercise
instructions through `NutritionPlan.workout_plan`; each instruction receives a stable response ID.

- `GET /workout-plans/assigned` — SELF reads the current seven-day assignment and completion.
- `PATCH /workout-plans/assigned/{workout_item_id}` — SELF marks or unmarks one instruction using
  `{ "completed": true }` or `{ "completed": false }`.
- `GET /coach/clients/{client_id}/workout-plans/assigned` — an accepted coach reads client progress.

The client dashboard exposes the same current progress through `assigned_workout_plan`. Legacy
standalone workout tables are archived by migration rather than deleted.

## Live weekly progress analytics

`GET /weekly-summary` returns seven Monday–Sunday graph points for the current week. It is computed
live and does not call the AI service.

- Workout score: cumulative completed assigned workout items divided by assigned workout items.
- Meal score: average capped attainment of configured calories, protein, carbs, fat, and fiber.
- Daily-goal score: completed assigned goals for that date divided by assigned goals.
- Combined score: equal-weight average of the applicable workout, meal, and daily-goal scores.

Future-day scores are `null`. Weekly averages use only elapsed, applicable days and include coverage
counts. `GET /weekly-summary` is the only weekly-summary endpoint; daily-goal mutation and persisted
AI narrative APIs were removed. Existing goal-completion records remain readable by analytics for
historical scoring.
