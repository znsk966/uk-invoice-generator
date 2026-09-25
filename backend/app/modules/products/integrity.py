"""Raw SQL for the catalog integrity triggers (defense in depth).

Same pattern as ``app.modules.invoices.immutability``: the DDL lives here so the
Alembic migration and the test harness (which builds the schema from metadata)
install exactly the same triggers and can never drift.

The API is the primary enforcement (PATCH accepts only ``unit_price``, no DELETE
route, the server copies description/VAT from the product onto linked lines).
These triggers fire even when a bug or a direct SQL statement bypasses the API.

Firing order on ``invoice_line``: Postgres fires triggers for the same event in
**alphabetical order of trigger name**. ``trg_invoice_line_immutable`` sorts
before ``trg_invoice_line_product_link``, so a write to a line of an issued
invoice is rejected by the immutability guard first; the link check only ever
runs on draft lines. Both raise, so the order changes only the error message,
never the outcome. Keep the names if you touch either trigger.
"""

PRODUCT_INTEGRITY_UP_SQL = """
-- A product's identity is immutable: only unit_price, archived_at and
-- updated_at may change. To change anything else, archive and create anew.
CREATE OR REPLACE FUNCTION guard_product_identity()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.owner_id IS DISTINCT FROM OLD.owner_id
       OR NEW.code IS DISTINCT FROM OLD.code
       OR NEW.description IS DISTINCT FROM OLD.description
       OR NEW.kind IS DISTINCT FROM OLD.kind
       OR NEW.vat_rate_code IS DISTINCT FROM OLD.vat_rate_code
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
    THEN
        RAISE EXCEPTION
            'product % identity is immutable: only unit_price and archived_at '
            'may change (archive this product and create a new one)',
            OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_product_identity
    BEFORE UPDATE ON product
    FOR EACH ROW EXECUTE FUNCTION guard_product_identity();


-- Products are archived, never deleted. The FK (ON DELETE RESTRICT) already
-- blocks deleting a referenced product; this also covers unreferenced ones.
CREATE OR REPLACE FUNCTION guard_product_no_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'product % cannot be deleted: archive it instead', OLD.id;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_product_no_delete
    BEFORE DELETE ON product
    FOR EACH ROW EXECUTE FUNCTION guard_product_no_delete();


-- A line linked to a product must belong to the product's owner and carry
-- exact copies of the product's (immutable) description and VAT rate code.
CREATE OR REPLACE FUNCTION guard_invoice_line_product_link()
RETURNS TRIGGER AS $$
DECLARE
    prod RECORD;
    inv_owner integer;
BEGIN
    SELECT owner_id, description, vat_rate_code INTO prod
    FROM product
    WHERE id = NEW.product_id;

    -- Unknown product or invoice: leave it to the foreign keys to reject.
    IF NOT FOUND THEN
        RETURN NEW;
    END IF;

    SELECT owner_id INTO inv_owner FROM invoice WHERE id = NEW.invoice_id;
    IF inv_owner IS NULL THEN
        RETURN NEW;
    END IF;

    IF prod.owner_id <> inv_owner THEN
        RAISE EXCEPTION
            'invoice_line cannot link product % owned by another user',
            NEW.product_id;
    END IF;

    IF NEW.description IS DISTINCT FROM prod.description THEN
        RAISE EXCEPTION
            'invoice_line description must equal product % description',
            NEW.product_id;
    END IF;

    IF NEW.vat_rate_code IS DISTINCT FROM prod.vat_rate_code THEN
        RAISE EXCEPTION
            'invoice_line vat_rate_code must equal product % vat_rate_code',
            NEW.product_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_invoice_line_product_link
    BEFORE INSERT OR UPDATE ON invoice_line
    FOR EACH ROW
    WHEN (NEW.product_id IS NOT NULL)
    EXECUTE FUNCTION guard_invoice_line_product_link();
"""

PRODUCT_INTEGRITY_DOWN_SQL = """
DROP TRIGGER IF EXISTS trg_invoice_line_product_link ON invoice_line;
DROP FUNCTION IF EXISTS guard_invoice_line_product_link();
DROP TRIGGER IF EXISTS trg_product_no_delete ON product;
DROP FUNCTION IF EXISTS guard_product_no_delete();
DROP TRIGGER IF EXISTS trg_product_identity ON product;
DROP FUNCTION IF EXISTS guard_product_identity();
"""
