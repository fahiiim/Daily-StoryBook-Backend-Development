from datetime import date

from pydantic import BaseModel, Field


class WeeklySummaryResponse(BaseModel):
    week_start: date
    week_end: date
    total_routines: int = Field(ge=0)
    completed_routines: int = Field(ge=0)
    completion_rate: float = Field(ge=0, le=100)
    average_water_intake: float | None = Field(default=None, ge=0)
    average_sleep: float | None = Field(default=None, ge=0)
    workout_entries: int = Field(ge=0)
    meal_entries: int = Field(ge=0)
    notes_entries: int = Field(ge=0)