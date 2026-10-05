from app.models.processing import Page

class PageService:
    def __init__(self, db_session):
        self.db = db_session
    
    def save_pages(self, document_version_id, pages: list[dict]) -> list[Page]:
        saved = []
        for p in pages:
            page = Page(
                document_version_id=document_version_id,
                page_number=p['page_number'],
                text=p['text'],
                extraction_type=p.get('extraction_type', 'docling')
            )
            self.db.add(page)
            saved.append(page)
        self.db.commit()
        for p in saved:
            self.db.refresh(p)
        return saved