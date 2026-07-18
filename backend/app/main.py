from fastapi import FastAPI

from app.core.db import check_db


def create_app() -> FastAPI:
    app = FastAPI(title="UK Invoice Generator", version="0.0.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "database": "ok" if check_db() else "unavailable",
        }

    return app


app = create_app()
