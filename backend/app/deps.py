from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_error
    return user


def require_roles(*allowed_roles: UserRole):
    """
    Dependency factory for role-gated endpoints, e.g.:
        @router.post(..., dependencies=[Depends(require_roles(UserRole.ADMIN))])
    """

    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return checker


def scoped_to_jurisdiction(user: User, state: str, district: str = None) -> bool:
    """
    True if `user`'s jurisdiction covers the given state/district.
    Admins and state officers see everything in their state;
    district officers are limited to their own district.
    """
    if user.role in (UserRole.ADMIN,):
        return True
    if user.role == UserRole.STATE_OFFICER:
        return user.state == state
    if user.role == UserRole.DISTRICT_OFFICER:
        return user.state == state and user.district == district
    return False
