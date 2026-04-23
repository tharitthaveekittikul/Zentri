import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, decode_token
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    SetupRequest,
    TokenResponse,
    UserResponse,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/setup", response_model=TokenResponse, status_code=201)
async def setup(request: SetupRequest, db: AsyncSession = Depends(get_db)):
    count = await auth_service.get_user_count(db)
    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ALREADY_SETUP",
        )
    user = await auth_service.create_user(db, request.username, request.password)
    access, refresh = auth_service.make_token_pair(user.id)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.authenticate_user(db, request.username, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    access, refresh = auth_service.make_token_pair(user.id)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/logout")
async def logout(_: User = Depends(get_current_user)):
    # Token invalidation via Redis blacklist added in Phase 3
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(request.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    user = await auth_service.get_user_by_id(db, uuid.UUID(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    access = create_access_token(subject=str(user.id))
    return AccessTokenResponse(access_token=access)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
