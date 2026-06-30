from pydantic import BaseModel, ConfigDict, Field


class TestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class TestRead(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)