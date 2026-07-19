"""Client endpoints. Archive semantics only — there is deliberately no DELETE."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import NOT_FOUND, AppError
from app.modules.clients.models import Client
from app.modules.clients.schemas import ClientCreate, ClientRead, ClientUpdate

router = APIRouter(prefix="/clients", tags=["clients"])


def _get_or_404(session: Session, client_id: int) -> Client:
    client = session.get(Client, client_id)
    if client is None:
        raise AppError(404, NOT_FOUND, f"Client {client_id} not found.")
    return client


@router.get("", response_model=list[ClientRead])
def list_clients(
    include_archived: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> list[Client]:
    stmt = select(Client).order_by(Client.id)
    if not include_archived:
        stmt = stmt.where(Client.archived_at.is_(None))
    return list(session.scalars(stmt))


@router.post("", response_model=ClientRead, status_code=201)
def create_client(payload: ClientCreate, session: Session = Depends(get_session)) -> Client:
    client = Client(**payload.model_dump())
    session.add(client)
    session.flush()
    return client


@router.get("/{client_id}", response_model=ClientRead)
def get_client(client_id: int, session: Session = Depends(get_session)) -> Client:
    return _get_or_404(session, client_id)


@router.put("/{client_id}", response_model=ClientRead)
def update_client(
    client_id: int, payload: ClientUpdate, session: Session = Depends(get_session)
) -> Client:
    client = _get_or_404(session, client_id)
    for field, value in payload.model_dump().items():
        setattr(client, field, value)
    session.flush()
    return client


@router.post("/{client_id}/archive", response_model=ClientRead)
def archive_client(client_id: int, session: Session = Depends(get_session)) -> Client:
    client = _get_or_404(session, client_id)
    # Idempotent: archiving an already-archived client leaves the timestamp as is.
    if client.archived_at is None:
        client.archived_at = datetime.now(UTC)
    session.flush()
    return client


@router.post("/{client_id}/unarchive", response_model=ClientRead)
def unarchive_client(client_id: int, session: Session = Depends(get_session)) -> Client:
    client = _get_or_404(session, client_id)
    client.archived_at = None
    session.flush()
    return client
