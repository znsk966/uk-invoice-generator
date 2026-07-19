"""Model registry.

Importing this module imports every ORM model, so that
``app.core.db.Base.metadata`` is fully populated. Alembic's ``env.py`` and the
test table-creation fixture both import it for this side effect.
"""

from app.core.db import Base
from app.modules.clients.models import Client
from app.modules.company.models import CompanyProfile
from app.modules.invoices.models import Invoice, InvoiceLine
from app.modules.numbering.models import NumberSequence
from app.modules.vat.models import VatRate

__all__ = [
    "Base",
    "Client",
    "CompanyProfile",
    "Invoice",
    "InvoiceLine",
    "NumberSequence",
    "VatRate",
]
