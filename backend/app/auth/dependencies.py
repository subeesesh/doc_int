import uuid
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.auth.security import decode_access_token
from app.models.user import User, UserRole, Role

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')
    user_id = payload.get('sub')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token payload')
    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found')
    return user

async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    """Returns user if authenticated, None otherwise. For endpoints that work with or without auth."""
    if not credentials:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload:
        return None
    user_id = payload.get('sub')
    if not user_id:
        return None
    return db.query(User).filter(User.id == uuid.UUID(user_id)).first()

def get_user_roles(user: User, db: Session) -> list[str]:
    """Get role names for a user."""
    user_roles = db.query(UserRole).filter(UserRole.user_id == user.id).all()
    role_ids = [ur.role_id for ur in user_roles]
    if not role_ids:
        return []
    roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
    return [r.name for r in roles]

def require_role(role_name: str):
    async def role_checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        roles = get_user_roles(user, db)
        if role_name not in roles and 'admin' not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Insufficient permissions')
        return user
    return role_checker

def get_accessible_document_ids(user: User, db: Session) -> list[str] | None:
    """Get document IDs the user can access. Returns None if admin (no filter needed)."""
    roles = get_user_roles(user, db)
    if 'admin' in roles:
        return None  # Admin can access all
    from app.models.document import Document, DocumentPermission
    # User owns the document OR has explicit permission
    owned = db.query(Document.id).filter(Document.user_id == user.id).all()
    permitted = db.query(DocumentPermission.document_id).filter(DocumentPermission.user_id == user.id).all()
    doc_ids = set(str(d[0]) for d in owned) | set(str(d[0]) for d in permitted)
    return list(doc_ids)
