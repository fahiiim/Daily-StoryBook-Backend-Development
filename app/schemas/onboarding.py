from typing import Literal

from pydantic import BaseModel


class OnboardingRoleRequest(BaseModel):
    role: Literal["SELF", "COACH"]
