import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User

logger = get_logger(__name__)


async def get_user_count(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(User))
    return result.scalar_one()


async def create_user(db: AsyncSession, username: str, password: str) -> User:
    user = User(
        id=uuid.uuid4(),
        username=username,
        password_hash=hash_password(password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("User created: username=%s id=%s", username, user.id)
    return user


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        logger.warning("Login failed — unknown username: %s", username)
        return None
    if not verify_password(password, user.password_hash):
        logger.warning("Login failed — wrong password: username=%s", username)
        return None
    logger.info("Login success: username=%s id=%s", username, user.id)
    return user


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


def make_token_pair(user_id: uuid.UUID) -> tuple[str, str]:
    access = create_access_token(subject=str(user_id))
    refresh = create_refresh_token(subject=str(user_id))
    return access, refresh
