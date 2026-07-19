"""Raw SQL for the invoice immutability triggers (defense in depth).

Kept here, not inline in the migration, so the exact same DDL is used both by
the Alembic migration and by the test harness that builds the schema from
metadata — the two can never drift. See CLAUDE.md: issued invoices are immutable.

These triggers are a tripwire, not the primary enforcement: the service layer
already blocks mutations of non-draft invoices with 409s. The triggers fire even
if a bug or a direct SQL statement bypasses the API.
"""

IMMUTABILITY_UP_SQL = """
CREATE OR REPLACE FUNCTION guard_invoice_immutable()
RETURNS TRIGGER AS $$
BEGIN
    -- Drafts are freely mutable (including the draft -> issued transition,
    -- where OLD.status is still 'draft').
    IF OLD.status = 'draft' THEN
        RETURN NEW;
    END IF;

    -- The one allowed change to a non-draft row: issued -> void, altering only
    -- status (and updated_at). Every other column must be unchanged.
    IF OLD.status = 'issued'
       AND NEW.status = 'void'
       AND NEW.id = OLD.id
       AND NEW.number IS NOT DISTINCT FROM OLD.number
       AND NEW.client_id = OLD.client_id
       AND NEW.invoice_date IS NOT DISTINCT FROM OLD.invoice_date
       AND NEW.tax_point_date IS NOT DISTINCT FROM OLD.tax_point_date
       AND NEW.due_date IS NOT DISTINCT FROM OLD.due_date
       AND NEW.currency = OLD.currency
       AND NEW.notes IS NOT DISTINCT FROM OLD.notes
       AND NEW.snapshot IS NOT DISTINCT FROM OLD.snapshot
       AND NEW.issued_at IS NOT DISTINCT FROM OLD.issued_at
       AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at
    THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION
        'invoice % is immutable (status=%): only issued->void is permitted',
        OLD.id, OLD.status;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_invoice_immutable
    BEFORE UPDATE ON invoice
    FOR EACH ROW EXECUTE FUNCTION guard_invoice_immutable();


-- A non-draft invoice can never be deleted. Drafts are scratch paper and remain
-- deletable (their lines cascade while the draft still exists).
CREATE OR REPLACE FUNCTION guard_invoice_no_delete()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status <> 'draft' THEN
        RAISE EXCEPTION
            'invoice % cannot be deleted (status=%): only drafts are deletable',
            OLD.id, OLD.status;
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_invoice_no_delete
    BEFORE DELETE ON invoice
    FOR EACH ROW EXECUTE FUNCTION guard_invoice_no_delete();


CREATE OR REPLACE FUNCTION guard_invoice_line_immutable()
RETURNS TRIGGER AS $$
DECLARE
    inv_status text;
BEGIN
    SELECT status::text INTO inv_status
    FROM invoice
    WHERE id = COALESCE(NEW.invoice_id, OLD.invoice_id);

    -- Parent already gone (e.g. cascade delete of a draft): nothing to protect.
    IF inv_status IS NULL THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    IF inv_status <> 'draft' THEN
        RAISE EXCEPTION
            'invoice_line of invoice % is immutable (invoice status=%)',
            COALESCE(NEW.invoice_id, OLD.invoice_id), inv_status;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- INSERT is covered too: a line may not be added to a non-draft invoice. The
-- function's COALESCE(NEW, OLD) already handles the INSERT case (OLD is null).
CREATE TRIGGER trg_invoice_line_immutable
    BEFORE INSERT OR UPDATE OR DELETE ON invoice_line
    FOR EACH ROW EXECUTE FUNCTION guard_invoice_line_immutable();
"""

IMMUTABILITY_DOWN_SQL = """
DROP TRIGGER IF EXISTS trg_invoice_line_immutable ON invoice_line;
DROP FUNCTION IF EXISTS guard_invoice_line_immutable();
DROP TRIGGER IF EXISTS trg_invoice_no_delete ON invoice;
DROP FUNCTION IF EXISTS guard_invoice_no_delete();
DROP TRIGGER IF EXISTS trg_invoice_immutable ON invoice;
DROP FUNCTION IF EXISTS guard_invoice_immutable();
"""
