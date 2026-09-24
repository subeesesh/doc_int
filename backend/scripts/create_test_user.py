import uuid

from app.db.database import SessionLocal
from app.models.user import User


def main() -> None:
    db = SessionLocal()

    try:
        user = User(
            id=uuid.uuid4(),
            name="Test User",
            email="test@enterprise.local",
            password_hash="test-password-hash",
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"User created: {user.id}")

    finally:
        db.close()


if __name__ == "__main__":
    main()