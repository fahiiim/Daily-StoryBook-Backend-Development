from pydantic import BaseModel, Field, model_validator


class StorybookGenerateRequest(BaseModel):
    name: str = Field(min_length=2)
    age: int = Field(ge=13, le=120)
    gender: str
    fitness_goal: str
    wake_up_time: str
    bed_time: str
    height: str | None = None
    weight: float | None = Field(default=None, ge=0)
    target_weight: float | None = Field(default=None, ge=0)
    bio: str | None = None
    fitness_motivation: str | None = None
    image_style: str | None = "ghibli_animation"


class RegeneratePageRequest(BaseModel):
    title: str | None = None
    story_text: str | None = None
    image_prompt: str | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if not any([
            self.title is not None,
            self.story_text is not None,
            self.image_prompt is not None,
        ]):
            raise ValueError("At least one field must be provided")
        return self


class RegenerateImageRequest(BaseModel):
    image_prompt: str = Field(min_length=1)
    image_style: str | None = "ghibli_animation"


class StorybookPageRegenerateRequest(RegeneratePageRequest):
    book_id: str = Field(min_length=1)
    page_id: int = Field(ge=1)


class StorybookImageRegenerateRequest(RegenerateImageRequest):
    book_id: str = Field(min_length=1)
    page_id: int = Field(ge=1)