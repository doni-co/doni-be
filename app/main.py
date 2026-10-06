from fastapi import FastAPI

from app.domains.auth.router import router as auth_router
from app.domains.datasets.router import router as datasets_router
from app.domains.ingestion.router import router as ingestion_router
from app.domains.media.router import router as media_router
from app.domains.pipelines.router import router as pipelines_router

app = FastAPI(title="doni-be")

app.include_router(auth_router)
app.include_router(ingestion_router)
app.include_router(media_router)
app.include_router(datasets_router)
app.include_router(pipelines_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
