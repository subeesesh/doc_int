"""Authentication endpoints."""
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, Role, UserRole
from app.auth.security import hash_password, verify_password, create_access_token
from app.auth.dependencies import get_current_user
from app.schemas.api import UserCreate, UserLogin, TokenResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/register", response_model=TokenResponse)
async def register(data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.flush()  # Ensure user.id is populated before creating UserRole

    # Ensure 'user' role exists and assign
    role = db.query(Role).filter(Role.name == "user").first()
    if not role:
        role = Role(name="user")
        db.add(role)
        db.flush()
    user_role = UserRole(user_id=user.id, role_id=role.id)
    db.add(user_role)
    db.commit()

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
    )


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return {"id": str(user.id), "name": user.name, "email": user.email}
