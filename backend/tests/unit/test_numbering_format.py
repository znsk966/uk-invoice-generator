"""Unit tests for the pure numbering helpers — no database."""

from app.core.numbering import format_invoice_number, invoice_sequence_key


def test_format_invoice_number_zero_pads_to_five():
    assert format_invoice_number(2026, 7) == "INV-2026-00007"
    assert format_invoice_number(2026, 1) == "INV-2026-00001"


def test_format_invoice_number_beyond_five_digits_does_not_truncate():
    assert format_invoice_number(2026, 123456) == "INV-2026-123456"


def test_invoice_sequence_key_is_per_year():
    assert invoice_sequence_key(2025) == "invoice-2025"
    assert invoice_sequence_key(2026) == "invoice-2026"
    assert invoice_sequence_key(2025) != invoice_sequence_key(2026)
