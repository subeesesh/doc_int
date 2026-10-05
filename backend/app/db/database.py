"""Database session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings

engine = create_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """Dependency for FastAPI endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()