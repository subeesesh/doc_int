from fastapi import FastAPI

from app.api.document import router as documents_router


app = FastAPI(
    title="Enterprise Document Intelligence",
    version="0.1.0",
)

app.include_router(documents_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
    }