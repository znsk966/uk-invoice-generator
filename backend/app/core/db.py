from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    Every model module registers its tables on this metadata; Alembic's
    ``target_metadata`` points here for autogenerate support.
    """


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yield a session, commit on success, roll back on error.

    The whole request handler runs inside this one transaction. Committing here
    (not in the service) is what makes the issue transition atomic: an exception
    raised anywhere in the handler rolls back *everything*, including an
    allocated invoice number, keeping numbering gapless.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_db() -> bool:
    """Return True if the database answers a trivial query, False otherwise.

    Never raises: a down or misconfigured database must not crash the caller.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
