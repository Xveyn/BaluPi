"""FastAPI dependency injection — auth & DB session."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_prefix}/auth/login",
    auto_error=False,
)


async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate Bearer token — forwards to NAS or checks local cache."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Try NAS token validation first (if reachable)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.nas_url}/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code == 200:
            data = resp.json()
            # Upsert user in local cache
            result = await db.execute(
                select(User).where(User.username == data.get("username"))
            )
            user = result.scalar_one_or_none()
            if not user:
                user = User(
                    id=str(uuid.uuid4()),
                    username=data["username"],
                    nas_user_id=str(data.get("id", "")),
                    last_auth=datetime.now(timezone.utc),
                )
                db.add(user)
            else:
                user.last_auth = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(user)
            return user
    except (httpx.HTTPError, Exception) as exc:
        logger.debug("NAS unreachable for token validation: %s", exc)

    # Fallback: decode JWT locally with shared secret
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.token_algorithm],
        )
        username: str | None = payload.get("sub") or payload.get("username")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: no subject claim",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not cached locally — login with NAS online first",
        )
    return user


async def get_current_user_optional(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Return user if token provided, else None."""
    if not token:
        return None
    try:
        return await get_current_user(request, token, db)
    except HTTPException:
        return None
