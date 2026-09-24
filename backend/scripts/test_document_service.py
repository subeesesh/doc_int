import uuid

from app.db.database import SessionLocal
from app.services.document_service import DocumentService


def main() -> None:
    db = SessionLocal()

    try:
        user_id = uuid.UUID("766e9fcf-980f-453c-b146-ac16e9f6696e")

        service = DocumentService()

        document = service.create_document(
            db,
            user_id=user_id,
            filename="sample.txt",
            data=b"Enterprise Document Intelligence test document.",
            content_type="text/plain",
        )

        print("Document created")
        print("Document ID:", document.id)
        print("Filename:", document.filename)
        print("Hash:", document.document_hash)
        print("Storage:", document.storage_path)

    finally:
        db.close()


if __name__ == "__main__":
    main()