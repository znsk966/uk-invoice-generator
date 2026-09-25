"""Product catalog service. Every function takes ``owner_id`` and filters on it
(Project Law rule 9): another user's product is 404 ``not_found``, never 403.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import is_unique_violation
from app.core.errors import NOT_FOUND, PRODUCT_CODE_TAKEN, AppError
from app.modules.products.models import Product


def get_product_or_404(session: Session, owner_id: int, product_id: int) -> Product:
    """Load one of ``owner_id``'s products (archived included) or raise 404."""
    product = session.scalar(
        select(Product).where(Product.id == product_id, Product.owner_id == owner_id)
    )
    if product is None:
        raise AppError(404, NOT_FOUND, f"Product {product_id} not found.")
    return product


def create_product(session: Session, owner_id: int, payload) -> Product:
    """Create a product. A duplicate ``code`` for this owner is 409.

    The insert runs in a savepoint so a unique violation — including one from a
    concurrent create that raced past the pre-check — rolls back only the
    savepoint and surfaces as 409 ``product_code_taken``, never a 500.
    """
    if _code_exists(session, owner_id, payload.code):
        raise _code_taken(payload.code)

    product = Product(owner_id=owner_id, **payload.model_dump())
    try:
        with session.begin_nested():
            session.add(product)
            session.flush()
    except IntegrityError as exc:
        if is_unique_violation(exc, "uq_product_owner_code"):
            raise _code_taken(payload.code) from exc
        raise
    return product


def _code_exists(session: Session, owner_id: int, code: str) -> bool:
    """The fast-path duplicate check. Not the guard — the constraint is."""
    stmt = select(Product.id).where(Product.owner_id == owner_id, Product.code == code)
    return session.scalar(stmt) is not None


def _code_taken(code: str) -> AppError:
    return AppError(409, PRODUCT_CODE_TAKEN, f"You already have a product with code {code!r}.")
