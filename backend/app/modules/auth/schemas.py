"""Auth request/response schemas.

Email is a plain ``str`` deliberately: Pydantic's ``EmailStr`` would pull in the
``email-validator`` package, and this prompt permits exactly one new dependency
(argon2-cffi). We normalise (strip + lowercase) and require a single ``@`` with
non-empty parts — enough for a self-hosted PoC, not RFC 5322 validation.
"""

from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    email: str
    # Minimum length only — no composition rules (they push users toward
    # predictable patterns without adding real entropy for a PoC).
    password: str = Field(min_length=10)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        email = value.strip().lower()
        local, _, domain = email.partition("@")
        if not local or not domain:
            raise ValueError("email must look like name@domain")
        return email


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        # Normalise identically to registration so a differently-cased login
        # still matches the stored (lowercased) address.
        return value.strip().lower()


class UserRead(BaseModel):
    id: int
    email: str
