from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import engine

app = FastAPI(
    title="GenAI Enterprise Lab API",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "name": "GenAI Enterprise Lab API",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            postgresql_version = connection.execute(
                text("SELECT current_setting('server_version')")
            ).scalar_one()

            pgvector_version = connection.execute(
                text(
                    """
                    SELECT extversion
                    FROM pg_extension
                    WHERE extname = 'vector'
                    """
                )
            ).scalar_one_or_none()

        return {
            "api": "healthy",
            "database": "healthy",
            "postgresql": postgresql_version,
            "pgvector": pgvector_version or "not_installed",
        }

    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "api": "healthy",
                "database": "unhealthy",
                "postgresql": None,
                "pgvector": None,
            },
        )
