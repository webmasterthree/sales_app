# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for field_sales.api.customers.invoice_items - prefilling a
complaint's claimed items from what was actually billed on a real invoice,
rather than asking the rep to re-pick items from the whole catalogue.

Uses real, already-submitted invoices already in the site rather than
creating new ones: Sales Invoice has an unrelated, pre-existing gap in this
bench (a DocType record - "Sales Invoice Export Document Item" - referencing
a Python module that was never installed, so _set_defaults() throws on
ANY new Sales Invoice insert regardless of what's actually set). Real
invoices that already exist don't go through that path again, so they're
unaffected and are what a real complaint would be filed against anyway."""

import frappe
from frappe.tests.utils import FrappeTestCase

from field_sales.api.customers import invoice_items

REP = "ravi.tsm@demo.local"
# Real, already-submitted invoices in the dev site (not created by this
# test) - one for a customer in the rep's own territory, one outside it.
IN_SCOPE_INVOICE = "SI-KOL0002/2026-2027"  # Golden Crust Foods, Kolkata Area
OUT_OF_SCOPE_INVOICE = "SI-KOL0006/2026-2027"  # Mumbai Cake House, Mumbai Area


class TestInvoiceItems(FrappeTestCase):
    def setUp(self):
        frappe.set_user(REP)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_returns_the_real_invoice_lines(self):
        if not frappe.db.exists("Sales Invoice", IN_SCOPE_INVOICE):
            self.skipTest(f"{IN_SCOPE_INVOICE} not present in this site's data")
        rows = invoice_items(IN_SCOPE_INVOICE)
        expected = frappe.get_all(
            "Sales Invoice Item", filters={"parent": IN_SCOPE_INVOICE},
            fields=["item_code", "qty", "amount"], order_by="idx asc",
        )
        self.assertTrue(rows)
        self.assertEqual(len(rows), len(expected))
        self.assertEqual(rows[0]["item_code"], expected[0]["item_code"])
        self.assertEqual(rows[0]["qty"], expected[0]["qty"])
        self.assertEqual(rows[0]["amount"], expected[0]["amount"])

    def test_refuses_an_invoice_for_a_customer_outside_the_reps_scope(self):
        """The rep's role has no real document-level read permission on
        Sales Invoice itself (only customer_ledger's own frappe.get_all
        bypasses that, by design) - this is gated through the invoice's own
        Customer instead, same convention customer_ledger already uses."""
        if not frappe.db.exists("Sales Invoice", OUT_OF_SCOPE_INVOICE):
            self.skipTest(f"{OUT_OF_SCOPE_INVOICE} not present in this site's data")
        with self.assertRaises(frappe.PermissionError):
            invoice_items(OUT_OF_SCOPE_INVOICE)

    def test_refuses_an_unknown_invoice(self):
        with self.assertRaises(frappe.PermissionError):
            invoice_items("SI-DOES-NOT-EXIST-0001")
