from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class GoogleAuthRequest(BaseModel):
    # Google OAuth access token from the frontend useGoogleLogin() popup.
    access_token: str
    # Role for a brand-new account only; ignored when the Google identity
    # resolves to an existing user.
    role: str = Field(default="user", pattern=r"^(user|partner)$")


class PartnerConfirmRequest(BaseModel):
    token: str
