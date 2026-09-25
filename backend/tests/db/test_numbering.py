"""DB tests for gapless numbering, including concurrency.

Numbering is per owner: ``allocate_number(session, owner_id, key)`` advances the
``(owner_id, key)`` sequence. Each test creates a real ``user`` row because
``number_sequence.owner_id`` is a NOT NULL FK.
"""

import threading
import uuid

from app.core.numbering import allocate_number, invoice_sequence_key
from app.modules.auth.models import User
from app.modules.numbering.models import NumberSequence


def _make_user(session) -> int:
    """Insert a throwaway user and return its id (owner for the sequence)."""
    user = User(email=f"num-{uuid.uuid4()}@test.local", password_hash="x")
    session.add(user)
    session.flush()
    return user.id


def _cleanup(session_factory, owner_id: int, *keys) -> None:
    with session_factory() as s:
        s.query(NumberSequence).filter(
            NumberSequence.owner_id == owner_id, NumberSequence.key.in_(keys)
        ).delete(synchronize_session=False)
        # number_sequence rows go first: the owner FK is ON DELETE RESTRICT.
        s.query(User).filter(User.id == owner_id).delete(synchronize_session=False)
        s.commit()


def test_sequential_allocation(db_session):
    owner_id = _make_user(db_session)
    key = "test-sequential"
    assert allocate_number(db_session, owner_id, key) == 1
    assert allocate_number(db_session, owner_id, key) == 2
    assert allocate_number(db_session, owner_id, key) == 3


def test_per_year_keys_are_isolated(db_session):
    owner_id = _make_user(db_session)
    key_2025 = invoice_sequence_key(2025)
    key_2026 = invoice_sequence_key(2026)
    # Each per-year sequence starts independently at 1.
    assert allocate_number(db_session, owner_id, key_2025) == 1
    assert allocate_number(db_session, owner_id, key_2026) == 1
    assert allocate_number(db_session, owner_id, key_2025) == 2
    assert allocate_number(db_session, owner_id, key_2026) == 2


def test_sequences_are_isolated_per_owner(db_session):
    # Two owners sharing the same key advance independently: both start at 1.
    owner_a = _make_user(db_session)
    owner_b = _make_user(db_session)
    key = invoice_sequence_key(2026)
    assert allocate_number(db_session, owner_a, key) == 1
    assert allocate_number(db_session, owner_b, key) == 1  # not 2 — separate sequence
    assert allocate_number(db_session, owner_a, key) == 2
    assert allocate_number(db_session, owner_b, key) == 2


def test_rollback_reuses_number(session_factory):
    # A rolled-back "issue" must not burn a number: the increment lives in the
    # same transaction and is undone, so the next allocation reuses the value.
    key = "test-rollback-reuse"
    with session_factory() as su:
        owner_id = _make_user(su)
        su.commit()
    try:
        with session_factory() as s1:
            assert allocate_number(s1, owner_id, key) == 1
            s1.rollback()  # simulate a failed issue

        with session_factory() as s2:
            assert allocate_number(s2, owner_id, key) == 1  # reused — gapless
            s2.commit()
    finally:
        _cleanup(session_factory, owner_id, key)


def test_concurrent_allocation_no_duplicate_no_gap(session_factory):
    # Two threads, two sessions, both allocating on the same key. The row-level
    # FOR UPDATE lock must serialise them: results are exactly {1, 2}.
    key = "test-concurrent"
    with session_factory() as su:
        owner_id = _make_user(su)
        su.commit()
    barrier = threading.Barrier(2)
    results: dict[int, int] = {}
    errors: list[Exception] = []

    def worker(worker_id: int) -> None:
        try:
            barrier.wait(timeout=10)
            with session_factory() as session:
                results[worker_id] = allocate_number(session, owner_id, key)
                session.commit()
        except Exception as exc:  # pragma: no cover - surfaced via assert below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)
        assert all(not t.is_alive() for t in threads), "an allocator thread hung"
        assert not errors, f"allocator raised: {errors}"
        assert sorted(results.values()) == [1, 2]  # no duplicate, no gap
    finally:
        _cleanup(session_factory, owner_id, key)
