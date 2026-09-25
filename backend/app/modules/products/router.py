"""Product catalog endpoints. Archive semantics only — there is no DELETE.

Every endpoint is scoped to the authenticated owner: another user's product is
404 ``not_found``, never 403. A product's identity (code, description, kind,
VAT rate) is immutable; only ``unit_price`` can be edited.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import PRODUCT_IMMUTABLE, AppError
from app.modules.auth.deps import current_user
from app.modules.auth.models import User
from app.modules.products import service
from app.modules.products.models import Product, ProductKind
from app.modules.products.schemas import (
    IMMUTABLE_FIELDS,
    ProductCreate,
    ProductPriceUpdate,
    ProductRead,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductRead])
def list_products(
    include_archived: bool = Query(default=False),
    kind: ProductKind | None = Query(default=None),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[Product]:
    stmt = select(Product).where(Product.owner_id == user.id).order_by(Product.code)
    if not include_archived:
        stmt = stmt.where(Product.archived_at.is_(None))
    if kind is not None:
        stmt = stmt.where(Product.kind == kind)
    return list(session.scalars(stmt))


@router.post("", response_model=ProductRead, status_code=201)
def create_product(
    payload: ProductCreate,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> Product:
    return service.create_product(session, user.id, payload)


@router.get("/{product_id}", response_model=ProductRead)
def get_product(
    product_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> Product:
    return service.get_product_or_404(session, user.id, product_id)


@router.patch(
    "/{product_id}",
    response_model=ProductRead,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": ProductPriceUpdate.model_json_schema()}},
        }
    },
)
def update_product_price(
    product_id: int,
    payload: dict[str, Any] = Body(),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> Product:
    """Change a product's default price — the only mutable field.

    The body is validated here rather than by FastAPI so the two kinds of bad
    request get distinct answers:

    * naming an identity field (``code``, ``description``, ``kind``,
      ``vat_rate_code``) is **409 ``product_immutable``** — a well-formed request
      for a change the catalog rule forbids;
    * an unknown field or an invalid ``unit_price`` is **422
      ``validation_failed``**, like any other malformed body.

    The price change affects only *new* lines: existing lines keep their own
    ``unit_price``, and issued invoices are frozen in their snapshot.
    """
    product = service.get_product_or_404(session, user.id, product_id)

    immutable = sorted(IMMUTABLE_FIELDS.intersection(payload))
    if immutable:
        named = ", ".join(immutable)
        raise AppError(
            409,
            PRODUCT_IMMUTABLE,
            f"{named} cannot be changed after creation — "
            "archive this product and create a new one.",
        )

    try:
        update = ProductPriceUpdate.model_validate(payload)
    except ValidationError as exc:
        # Hand off to the global handler: same 422 validation_failed shape as
        # every other endpoint. Prefix locations with "body" as FastAPI does.
        raise RequestValidationError(
            [{**err, "loc": ("body", *err["loc"])} for err in exc.errors()]
        ) from exc

    product.unit_price = update.unit_price
    session.flush()
    return product


@router.post("/{product_id}/archive", response_model=ProductRead)
def archive_product(
    product_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> Product:
    product = service.get_product_or_404(session, user.id, product_id)
    # Idempotent: re-archiving leaves the original timestamp in place.
    if product.archived_at is None:
        product.archived_at = datetime.now(UTC)
    session.flush()
    return product


@router.post("/{product_id}/unarchive", response_model=ProductRead)
def unarchive_product(
    product_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> Product:
    product = service.get_product_or_404(session, user.id, product_id)
    product.archived_at = None
    session.flush()
    return product
