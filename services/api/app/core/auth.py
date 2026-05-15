import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.models.users import User, UserRole


async def _get_or_create_dev_user(db: AsyncSession, dev_user_id: str | None) -> User:
    if dev_user_id:
        try:
            uid = uuid.UUID(dev_user_id)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid X-Dev-User-Id") from e
        existing = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if existing:
            return existing

    email = f"dev+{(dev_user_id or 'default')}@virtual-stylist.local"
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        return existing

    user = User(
        id=uuid.UUID(dev_user_id) if dev_user_id else uuid.uuid4(),
        email=email,
        role=UserRole.guardian,
        display_name="Dev User",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    x_dev_user_id: Annotated[str | None, Header()] = None,
) -> User:
    settings = get_settings()

    if settings.dev_auth_bypass:
        return await _get_or_create_dev_user(db, x_dev_user_id)

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")

    # Production path: verify JWT against AUTH_JWKS_URL, claims → User row.
    # Wire python-jose + JWKS cache here once Auth0/Clerk tenant exists.
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "configure AUTH_JWKS_URL")


CurrentUser = Annotated[User, Depends(get_current_user)]
