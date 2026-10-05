"""Seed initial users, roles, and default configuration."""
import uuid
from app.db.database import SessionLocal
from app.models.user import User, Role, UserRole
from app.auth.security import hash_password
from app.storage.minio_client import minio_service
from app.vectorstore.qdrant_client import qdrant_service
from app.search.elasticsearch import ElasticsearchService
from app.config.settings import settings


def main():
    print("=" * 60)
    print("SEEDING INITIAL PLATFORM DATA")
    print("=" * 60)

    db = SessionLocal()
    try:
        # 1. Ensure MinIO bucket
        minio_service._ensure_bucket()
        print(f"[OK] MinIO bucket '{settings.MINIO_BUCKET}' verified.")

        # 2. Ensure Qdrant collection
        qdrant_service.ensure_collection()
        print(f"[OK] Qdrant collection '{settings.QDRANT_COLLECTION}' verified.")

        # 3. Ensure Elasticsearch index if reachable
        try:
            es = ElasticsearchService(host=settings.ELASTICSEARCH_HOST, port=settings.ELASTICSEARCH_PORT)
            es.ensure_index()
            print(f"[OK] Elasticsearch index '{settings.ELASTICSEARCH_INDEX}' verified.")
        except Exception as e:
            print(f"[WARN] Elasticsearch index check skipped: {e}")

        # 4. Roles & Users
        for r_name in ["admin", "user", "viewer"]:
            role = db.query(Role).filter(Role.name == r_name).first()
            if not role:
                role = Role(id=uuid.uuid4(), name=r_name)
                db.add(role)
        db.commit()

        admin_role = db.query(Role).filter(Role.name == "admin").first()
        user_role = db.query(Role).filter(Role.name == "user").first()

        admin = db.query(User).filter(User.email == "admin@enterprise.local").first()
        if not admin:
            admin = User(
                id=uuid.uuid4(),
                name="System Administrator",
                email="admin@enterprise.local",
                password_hash=hash_password("admin123"),
            )
            db.add(admin)
            db.flush()
            db.add(UserRole(user_id=admin.id, role_id=admin_role.id))

        user = db.query(User).filter(User.email == "user@enterprise.local").first()
        if not user:
            user = User(
                id=uuid.uuid4(),
                name="Enterprise User",
                email="user@enterprise.local",
                password_hash=hash_password("user123"),
            )
            db.add(user)
            db.flush()
            db.add(UserRole(user_id=user.id, role_id=user_role.id))

        db.commit()
        print("[OK] Default Admin and User seeded.")
        print("=" * 60)
        print("SEEDING COMPLETE")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    main()
