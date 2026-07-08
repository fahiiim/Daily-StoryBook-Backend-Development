from pydantic import BaseModel, EmailStr, Field, model_validator


class VerificationCodeRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=255)
    confirm_password: str = Field(min_length=8, max_length=255)

    @model_validator(mode="after")
    def validate_password_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password must match")
        return self


class MessageResponse(BaseModel):
    message: str
