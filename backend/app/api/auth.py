"""
/auth/login + /auth/me endpoints.

Master switch via env ASTRA_AUTH_ENABLED. When OFF (default), all requests
are accepted as role 'admin' so the demo flows still work without login.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.auth import (
    Operator, authenticate, auth_enabled, auth_required, issue_token,
    list_known_operators, ttl_seconds,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    operator_id: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_at: int
    operator_id: str
    role: str


class MeOut(BaseModel):
    operator_id: str
    role: str
    auth_enabled: bool


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn) -> LoginOut:
    role = authenticate(body.operator_id, body.password)
    if role is None:
        raise HTTPException(401, "invalid operator_id or password")
    token, exp = issue_token(body.operator_id, role)
    return LoginOut(
        access_token=token,
        expires_at=exp,
        operator_id=body.operator_id,
        role=role,
    )


@router.get("/me", response_model=MeOut)
def me(op: Operator = Depends(auth_required)) -> MeOut:
    return MeOut(operator_id=op.id, role=op.role, auth_enabled=auth_enabled())


@router.get("/operators")
def operators() -> dict:
    """List of valid operator_ids (no hashes). Useful for the login dropdown."""
    return {
        "operators": list_known_operators(),
        "auth_enabled": auth_enabled(),
        "ttl_seconds": ttl_seconds(),
    }
