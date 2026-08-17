from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from fastapi import Depends

from ..config import get_settings
from ..schemas import TokenResponse
from ..security import authenticate_demo_user, create_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()


@router.post("/token", response_model=TokenResponse)
def issue_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> TokenResponse:
    if not authenticate_demo_user(form_data.username, form_data.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    token = create_access_token(subject=form_data.username)
    return TokenResponse(access_token=token, expires_in_minutes=settings.jwt_expiry_minutes)
