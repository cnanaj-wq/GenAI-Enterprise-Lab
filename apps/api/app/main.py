from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import engine
from .routes.finops import router as finops_router
from .routes.investigations import router as investigations_router
from .routes.mcp_gateway import router as mcp_router
from .routes.optimize import router as optimize_router
from .routes.project_health import router as project_health_router

app = FastAPI(
    title="GenAI Enterprise Lab API",
    version="0.6.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(investigations_router)
app.include_router(mcp_router)
app.include_router(project_health_router)
app.include_router(optimize_router)
app.include_router(finops_router)


@app.get("/")
def root():
    return {
        "name": "GenAI Enterprise Lab API",
        "version": "0.6.0",
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
