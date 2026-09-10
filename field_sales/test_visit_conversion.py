# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for turning a Field Visit into a Sales Order - both the read-only
prefill the order form now uses (visit_order_prefill) and the older
create-immediately path (convert_visit_to_order) kept for other callers.
Both share the same guard/pricing logic (_prepare_visit_conversion), so the
guard tests below apply to either."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from field_sales.api.catalog import convert_visit_to_order, visit_customer_context, visit_order_prefill

REP = "ravi.tsm@demo.local"
PRICE_LIST = "Standard Selling"
LIST_RATE = 500.0


def ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.new_doc(doctype)
    doc.update(values)
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


class TestVisitConversion(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = frappe.db.get_value("Employee", {"user_id": REP, "status": "Active"}, "name")
        cls.customer = ensure("Customer", "FS Test Visit Conversion Customer", {
            "customer_name": "FS Test Visit Conversion Customer",
            "customer_group": "Commercial", "territory": "Kolkata Area",
        })
        shop = frappe.get_all("Shop", limit=1, pluck="name")
        frappe.db.set_value("Customer", cls.customer, {
            "default_price_list": PRICE_LIST,
            "custom_shop": shop[0] if shop else None,
        })
        cls.reason = ensure("Field Reason", "FS Test Visit Conversion Reason", {
            "reason": "FS Test Visit Conversion Reason", "applies_to": "Visit",
        })
        hsn = frappe.get_all("GST HSN Code", limit=1, pluck="name")
        cat = frappe.get_all("Item Category", limit=1, pluck="name")
        cls.item = ensure("Item", "FS-TEST-VISITCONV-ITEM", {
            "item_code": "FS-TEST-VISITCONV-ITEM", "item_name": "FS Test Visit Conversion Item",
            "item_group": "All Item Groups", "stock_uom": "Kg",
            "is_stock_item": 0, "is_sales_item": 1,
            "gst_hsn_code": hsn[0] if hsn else None,
            "item_category": cat[0] if cat else None,
        })
        cls.unpriced_item = ensure("Item", "FS-TEST-VISITCONV-UNPRICED", {
            "item_code": "FS-TEST-VISITCONV-UNPRICED", "item_name": "FS Test Visit Conversion Unpriced",
            "item_group": "All Item Groups", "stock_uom": "Kg",
            "is_stock_item": 0, "is_sales_item": 1,
            "gst_hsn_code": hsn[0] if hsn else None,
            "item_category": cat[0] if cat else None,
        })
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._clear_prices()
        self._price(LIST_RATE)
        self._cleanup()
        frappe.set_user(REP)

    def tearDown(self):
        frappe.set_user("Administrator")
        self._cleanup()
        self._clear_prices()
        frappe.db.rollback()

    def _clear_prices(self):
        for name in frappe.get_all("Item Price", {"item_code": self.item}, pluck="name"):
            frappe.delete_doc("Item Price", name, force=True, ignore_permissions=True)

    def _price(self, rate):
        doc = frappe.new_doc("Item Price")
        doc.update({
            "item_code": self.item, "price_list": PRICE_LIST,
            "price_list_rate": rate, "uom": "Kg", "currency": "INR",
        })
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)

    def _cleanup(self):
        for name in frappe.get_all("Sales Order", {"customer": self.customer}, pluck="name"):
            doc = frappe.get_doc("Sales Order", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Sales Order", name, force=True, ignore_permissions=True)
        for name in frappe.get_all("Field Visit", {"customer": self.customer}, pluck="name"):
            if frappe.db.get_value("Field Visit", name, "docstatus") == 1:
                frappe.db.set_value("Field Visit", name, "docstatus", 0)
            frappe.delete_doc("Field Visit", name, force=True, ignore_permissions=True)

    def _visit(self, docstatus=1, order_status="With Order", party_type="Customer", pitched_items=None):
        doc = frappe.new_doc("Field Visit")
        doc.update({
            "party_type": party_type,
            "customer": self.customer if party_type == "Customer" else None,
            "prospect_name": "FS Test Visit Conversion Prospect" if party_type == "Prospect" else None,
            "visit_date": nowdate(),
            "order_status": order_status,
            "reason": self.reason if order_status == "Without Order" else None,
            "sales_person": self.employee,
        })
        if pitched_items is None:
            pitched_items = [{"item_code": self.item, "qty": 3, "uom": "Kg"}]
        for row in pitched_items:
            doc.append("pitched_items", row)
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        if docstatus == 1:
            frappe.db.set_value("Field Visit", doc.name, "docstatus", 1)
            doc.reload()
        return doc

    # -------------------------------------------------------- prefill

    def test_prefill_returns_customer_and_priced_items(self):
        visit = self._visit()
        result = visit_order_prefill(visit.name)
        self.assertEqual(result["customer"], self.customer)
        self.assertEqual(result["fs_field_visit"], visit.name)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["item_code"], self.item)
        self.assertEqual(result["items"][0]["rate"], LIST_RATE)

    def test_prefill_creates_nothing(self):
        """The whole point of prefill over the old immediate-convert path -
        the rep reviews on the real order form before anything is saved."""
        visit = self._visit()
        visit_order_prefill(visit.name)
        self.assertFalse(frappe.db.exists("Sales Order", {"fs_field_visit": visit.name}))

    def test_prefill_includes_unpriced_items_for_manual_rate(self):
        """An unpriced pitched item used to be silently dropped (or block the
        whole conversion if it was the only one) - it's now included with
        rate=None so the order form's existing manual-rate input picks it up,
        same as a manually-added unpriced item already gets."""
        visit = self._visit(pitched_items=[
            {"item_code": self.item, "qty": 3, "uom": "Kg"},
            {"item_code": self.unpriced_item, "qty": 1, "uom": "Kg"},
        ])
        result = visit_order_prefill(visit.name)
        self.assertEqual(len(result["items"]), 2)
        priced = next(i for i in result["items"] if i["item_code"] == self.item)
        unpriced = next(i for i in result["items"] if i["item_code"] == self.unpriced_item)
        self.assertEqual(priced["rate"], LIST_RATE)
        self.assertIsNone(unpriced["rate"])
        self.assertIn(self.unpriced_item, result["remarks"])

    def test_prefill_succeeds_when_the_only_pitched_item_is_unpriced(self):
        """The real bug this covers: a visit with exactly one pitched item
        and no price for it used to refuse the whole conversion outright -
        customer/contact never reached the order form either. It now
        succeeds, with that one item awaiting a manual rate."""
        visit = self._visit(pitched_items=[{"item_code": self.unpriced_item, "qty": 1, "uom": "Kg"}])
        result = visit_order_prefill(visit.name)
        self.assertEqual(result["customer"], self.customer)
        self.assertEqual(len(result["items"]), 1)
        self.assertIsNone(result["items"][0]["rate"])

    def test_prefill_refuses_a_visit_with_no_pitched_items_at_all(self):
        visit = self._visit(pitched_items=[])
        with self.assertRaises(frappe.ValidationError):
            visit_order_prefill(visit.name)

    def test_prefill_refuses_a_draft_visit(self):
        visit = self._visit(docstatus=0)
        with self.assertRaises(frappe.ValidationError):
            visit_order_prefill(visit.name)

    def test_prefill_refuses_a_prospect(self):
        visit = self._visit(party_type="Prospect")
        with self.assertRaises(frappe.ValidationError):
            visit_order_prefill(visit.name)

    def test_prefill_refuses_a_secondary_customer(self):
        """A Secondary customer's orders belong on the Channel Partner
        flow (Secondary Sales Order), not a Direct Customer order - same
        rule as the order form's own Customer picker being Primary-only."""
        channel_partner = ensure("Customer", "FS Test Visit Conversion CP", {
            "customer_name": "FS Test Visit Conversion CP",
            "customer_group": "Commercial", "territory": "Kolkata Area",
        })
        secondary = ensure("Customer", "FS Test Visit Conversion Secondary", {
            "customer_name": "FS Test Visit Conversion Secondary",
            "customer_group": "Commercial", "territory": "Kolkata Area",
        })
        frappe.db.set_value("Customer", secondary, {
            "customer_level": "Secondary",
            "custom_channel_partner": channel_partner,
        })
        visit = frappe.new_doc("Field Visit")
        visit.update({
            "party_type": "Customer", "customer": secondary, "visit_date": nowdate(),
            "order_status": "With Order", "sales_person": self.employee,
        })
        visit.append("pitched_items", {"item_code": self.item, "qty": 3, "uom": "Kg"})
        visit.flags.ignore_mandatory = True
        visit.insert(ignore_permissions=True)
        frappe.db.set_value("Field Visit", visit.name, "docstatus", 1)
        try:
            with self.assertRaises(frappe.ValidationError):
                visit_order_prefill(visit.name)
        finally:
            frappe.db.set_value("Field Visit", visit.name, "docstatus", 0)
            frappe.delete_doc("Field Visit", visit.name, force=True, ignore_permissions=True)
            frappe.delete_doc("Customer", secondary, force=True, ignore_permissions=True)
            frappe.delete_doc("Customer", channel_partner, force=True, ignore_permissions=True)

    def test_prefill_refuses_without_order(self):
        visit = self._visit(order_status="Without Order")
        with self.assertRaises(frappe.ValidationError):
            visit_order_prefill(visit.name)

    def test_prefill_refuses_an_already_converted_visit(self):
        visit = self._visit()
        convert_visit_to_order(visit.name)
        with self.assertRaises(frappe.ValidationError):
            visit_order_prefill(visit.name)

    # -------------------------------------------------- convert (regression)
    #
    # convert_visit_to_order still exists for any other caller - these prove
    # splitting out _prepare_visit_conversion didn't change its behaviour.

    def test_convert_still_creates_a_real_draft_order(self):
        visit = self._visit()
        result = convert_visit_to_order(visit.name)
        doc = frappe.get_doc("Sales Order", result["name"])
        self.assertEqual(doc.docstatus, 0)
        self.assertEqual(doc.fs_field_visit, visit.name)
        self.assertEqual(doc.items[0].item_code, self.item)
        self.assertEqual(flt_(doc.items[0].rate), LIST_RATE)

    def test_convert_refuses_a_second_conversion(self):
        visit = self._visit()
        convert_visit_to_order(visit.name)
        with self.assertRaises(frappe.ValidationError):
            convert_visit_to_order(visit.name)

    def test_convert_still_refuses_when_the_only_item_is_unpriced(self):
        """Unlike visit_order_prefill, this immediate-create path has no
        review step for the rep to enter a manual rate, so it keeps refusing
        outright when nothing priced survives - matching its own docstring."""
        visit = self._visit(pitched_items=[{"item_code": self.unpriced_item, "qty": 1, "uom": "Kg"}])
        with self.assertRaises(frappe.ValidationError):
            convert_visit_to_order(visit.name)

    # --------------------------------------------- customer context bypass
    #
    # Real production bug: A & B Enterprises' own Customer.territory field
    # ("Area" in the UI) pointed at a territory no longer inside its rep's
    # own User Permission scope, even though the rep's Field Visit against
    # that same customer was filed under a territory they do hold - blocking
    # the order form from even loading the customer once conversion started.

    def test_visit_customer_context_bypasses_a_stale_customer_territory(self):
        frappe.set_user("Administrator")
        mismatched = ensure("Territory", "FS Test Visit Conversion Mismatched Territory", {
            "territory_name": "FS Test Visit Conversion Mismatched Territory",
            "parent_territory": "All Territories", "is_group": 0,
        })
        frappe.db.set_value("Customer", self.customer, "territory", mismatched)
        perm_exists = frappe.db.exists(
            "User Permission", {"user": REP, "allow": "Territory", "for_value": "Kolkata Area"}
        )
        if not perm_exists:
            perm = frappe.new_doc("User Permission")
            perm.update({"user": REP, "allow": "Territory", "for_value": "Kolkata Area", "apply_to_all_doctypes": 1})
            perm.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.set_user(REP)
        try:
            visit = self._visit()
            frappe.set_user("Administrator")
            frappe.db.set_value("Field Visit", visit.name, "territory", "Kolkata Area")
            frappe.set_user(REP)

            # Sanity check: the mismatch is real - a plain Customer read is refused.
            with self.assertRaises(frappe.PermissionError):
                frappe.get_doc("Customer", self.customer).check_permission("read")

            result = visit_customer_context(visit.name)
            self.assertEqual(result["name"], self.customer)
        finally:
            frappe.set_user("Administrator")
            frappe.db.set_value("Customer", self.customer, "territory", "Kolkata Area")
            if not perm_exists:
                frappe.db.delete("User Permission", {"user": REP, "allow": "Territory", "for_value": "Kolkata Area"})
            frappe.db.commit()
            frappe.set_user(REP)

    def test_visit_customer_context_still_requires_visit_access(self):
        """The bypass is earned by check_permission on the Visit itself -
        confirm it still refuses a visit this user has no read access to.
        Scopes REP to "Kolkata Area" only for the duration of this test so
        the result doesn't depend on whichever other tests already ran (a
        user with zero User Permission rows at all is unrestricted, so this
        needs its own explicit, self-contained scoping)."""
        frappe.set_user("Administrator")
        perm_exists = frappe.db.exists(
            "User Permission", {"user": REP, "allow": "Territory", "for_value": "Kolkata Area"}
        )
        if not perm_exists:
            perm = frappe.new_doc("User Permission")
            perm.update({"user": REP, "allow": "Territory", "for_value": "Kolkata Area", "apply_to_all_doctypes": 1})
            perm.insert(ignore_permissions=True)

        other_employee = frappe.db.get_value(
            "Employee", {"user_id": "priya.tsm@demo.local", "status": "Active"}, "name"
        )
        visit = frappe.new_doc("Field Visit")
        visit.update({
            "party_type": "Customer", "customer": self.customer, "visit_date": nowdate(),
            "order_status": "With Order", "sales_person": other_employee or self.employee,
            "territory": "Howrah Area",
        })
        visit.append("pitched_items", {"item_code": self.item, "qty": 1, "uom": "Kg"})
        visit.flags.ignore_mandatory = True
        visit.insert(ignore_permissions=True)
        frappe.db.set_value("Field Visit", visit.name, "docstatus", 1)
        frappe.db.commit()

        frappe.set_user(REP)
        try:
            with self.assertRaises(frappe.PermissionError):
                visit_customer_context(visit.name)
        finally:
            frappe.set_user("Administrator")
            frappe.db.set_value("Field Visit", visit.name, "docstatus", 0)
            frappe.delete_doc("Field Visit", visit.name, force=True, ignore_permissions=True)
            if not perm_exists:
                frappe.db.delete("User Permission", {"user": REP, "allow": "Territory", "for_value": "Kolkata Area"})
            frappe.db.commit()
            frappe.set_user(REP)


def flt_(v):
    from frappe.utils import flt
    return flt(v, 2)
