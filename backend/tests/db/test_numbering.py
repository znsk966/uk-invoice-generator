"""DB tests for gapless numbering, including concurrency."""

import threading

from app.core.numbering import allocate_number, invoice_sequence_key
from app.modules.numbering.models import NumberSequence


def _cleanup(session_factory, *keys):
    with session_factory() as s:
        s.query(NumberSequence).filter(NumberSequence.key.in_(keys)).delete(
            synchronize_session=False
        )
        s.commit()


def test_sequential_allocation(db_session):
    key = "test-sequential"
    assert allocate_number(db_session, key) == 1
    assert allocate_number(db_session, key) == 2
    assert allocate_number(db_session, key) == 3


def test_per_year_keys_are_isolated(db_session):
    key_2025 = invoice_sequence_key(2025)
    key_2026 = invoice_sequence_key(2026)
    # Each per-year sequence starts independently at 1.
    assert allocate_number(db_session, key_2025) == 1
    assert allocate_number(db_session, key_2026) == 1
    assert allocate_number(db_session, key_2025) == 2
    assert allocate_number(db_session, key_2026) == 2


def test_rollback_reuses_number(session_factory):
    # A rolled-back "issue" must not burn a number: the increment lives in the
    # same transaction and is undone, so the next allocation reuses the value.
    key = "test-rollback-reuse"
    try:
        with session_factory() as s1:
            assert allocate_number(s1, key) == 1
            s1.rollback()  # simulate a failed issue

        with session_factory() as s2:
            assert allocate_number(s2, key) == 1  # reused — gapless
            s2.commit()
    finally:
        _cleanup(session_factory, key)


def test_concurrent_allocation_no_duplicate_no_gap(session_factory):
    # Two threads, two sessions, both allocating on the same key. The row-level
    # FOR UPDATE lock must serialise them: results are exactly {1, 2}.
    key = "test-concurrent"
    barrier = threading.Barrier(2)
    results: dict[int, int] = {}
    errors: list[Exception] = []

    def worker(worker_id: int) -> None:
        try:
            barrier.wait(timeout=10)
            with session_factory() as session:
                results[worker_id] = allocate_number(session, key)
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
        _cleanup(session_factory, key)
