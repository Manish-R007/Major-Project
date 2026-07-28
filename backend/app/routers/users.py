from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import User, UserRole, AuditLog
from app.schemas import UserOut, AdminUserCreate
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get(
    "/",
    response_model=list[UserOut],
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.STATE_OFFICER))],
)
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()


@router.post(
    "/",
    response_model=UserOut,
    status_code=201,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def create_official(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Admin-only account provisioning for officials (village/district/state
    roles). This is the intended way to create non-Citizen accounts —
    see UserCreate's docstring in schemas.py for why public
    self-registration doesn't accept a role field.
    """
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        state=payload.state,
        district=payload.district,
        village=payload.village,
    )
    db.add(user)
    db.add(AuditLog(user_id=current_user.id, action="official_account_created",
                     entity_type="user", detail=f"created {payload.username} as {payload.role.value}"))
    db.commit()
    db.refresh(user)
    return user
