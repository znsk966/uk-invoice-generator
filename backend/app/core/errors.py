"""Uniform error handling for the API.

Every handled error is rendered as::

    {"detail": {"code": "<machine_code>", "message": "<human message>"}}

so the (Phase 3) frontend can branch on a stable machine ``code`` rather than
parsing prose or guessing from HTTP status alone.
"""

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Machine codes (stable contract with the frontend). Keep in sync with the table
# in docs/ARCHITECTURE.md.
NOT_FOUND = "not_found"
CLIENT_ARCHIVED = "client_archived"
INVOICE_NOT_DRAFT = "invoice_not_draft"
INVOICE_NOT_ISSUED = "invoice_not_issued"
VALIDATION_FAILED = "validation_failed"
COMPANY_PROFILE_MISSING = "company_profile_missing"


class AppError(Exception):
    """A domain error that maps to a specific HTTP status and machine code."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _body(code: str, message: str) -> dict:
    """The one error body shape, built in one place so it cannot drift."""
    return {"detail": {"code": code, "message": message}}


def register_error_handlers(app: FastAPI) -> None:
    """Attach the handlers that produce the uniform error shape."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Collapse Pydantic/body validation failures into our shape. The full
        # error list is preserved under "errors" for debugging, but clients
        # branch on the stable code.
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": VALIDATION_FAILED,
                    "message": "Request validation failed.",
                    "errors": jsonable_encoder(exc.errors()),
                }
            },
        )
