from fastapi import APIRouter, FastAPI

from app.core.db import check_db
from app.core.errors import register_error_handlers
from app.modules.clients.router import router as clients_router
from app.modules.company.router import router as company_router
from app.modules.invoices.router import router as invoices_router


def create_app() -> FastAPI:
    app = FastAPI(title="UK Invoice Generator", version="0.0.0")

    register_error_handlers(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "database": "ok" if check_db() else "unavailable",
        }

    api = APIRouter(prefix="/api/v1")
    api.include_router(clients_router)
    api.include_router(company_router)
    api.include_router(invoices_router)
    app.include_router(api)

    return app


app = create_app()
