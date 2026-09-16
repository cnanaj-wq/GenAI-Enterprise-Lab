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
            connection.execute(text("SELECT 1"))

        return {
            "api": "healthy",
            "database": "healthy",
        }

    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "api": "healthy",
                "database": "unhealthy",
            },
        )
