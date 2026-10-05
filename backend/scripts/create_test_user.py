"""Create test users and assign roles."""
import sys
import uuid
from app.db.database import SessionLocal
from app.models.user import User, Role, UserRole
from app.auth.security import hash_password


def create_or_update_user(db, name: str, email: str, password: str, role_name: str = "user"):
    # Ensure role exists
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(id=uuid.uuid4(), name=role_name)
        db.add(role)
        db.flush()

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            id=uuid.uuid4(),
            name=name,
            email=email,
            password_hash=hash_password(password),
        )
        db.add(user)
        db.flush()
        print(f"Created user: {user.email} (ID: {user.id})")
    else:
        user.password_hash = hash_password(password)
        print(f"User {user.email} exists, updated password.")

    # Assign role if not already assigned
    ur = db.query(UserRole).filter(UserRole.user_id == user.id, UserRole.role_id == role.id).first()
    if not ur:
        ur = UserRole(user_id=user.id, role_id=role.id)
        db.add(ur)

    db.commit()
    return user


def main():
    db = SessionLocal()
    try:
        # Create Admin
        admin = create_or_update_user(db, "System Admin", "admin@enterprise.local", "admin123", "admin")
        # Create Regular User
        test_user = create_or_update_user(db, "Regular User", "user@enterprise.local", "user123", "user")

        print("=" * 60)
        print("TEST USERS READY:")
        print("  Admin: admin@enterprise.local / admin123 (Role: admin)")
        print("  User:  user@enterprise.local  / user123  (Role: user)")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    main()