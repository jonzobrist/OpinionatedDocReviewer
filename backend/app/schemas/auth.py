from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class AuthRegisterRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64)
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    role: str = Field(default="reader", max_length=32)


class AuthRegisterResponse(BaseModel):
    user_id: int
    email: EmailStr
    requires_email_verification: bool = True
    verification_token: str | None = None


class AuthVerifyEmailRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64)
    email: EmailStr
    token: str = Field(min_length=10, max_length=500)


class AuthLoginRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64)
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class AuthLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user_id: int
    role: str
    email: EmailStr


class AuthLogoutResponse(BaseModel):
    ok: bool = True


class AuthForgotPasswordRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64)
    email: EmailStr


class AuthForgotPasswordResponse(BaseModel):
    ok: bool = True
    reset_token: str | None = None


class AuthMfaChallengeRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64)
    email: EmailStr
    purpose: str = Field(min_length=1, max_length=64)


class AuthMfaChallengeResponse(BaseModel):
    challenge_id: int
    expires_in_seconds: int
    code: str | None = None


class AuthMfaVerifyRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64)
    challenge_id: int = Field(gt=0)
    code: str = Field(min_length=4, max_length=20)


class AuthMfaVerifyResponse(BaseModel):
    ok: bool = True


class AuthResetPasswordRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64)
    email: EmailStr
    reset_token: str = Field(min_length=10, max_length=500)
    new_password: str = Field(min_length=8, max_length=200)
    mfa_challenge_id: int = Field(gt=0)


class AuthGenericResponse(BaseModel):
    ok: bool = True
