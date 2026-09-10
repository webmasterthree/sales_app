# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the Channel Partner order write path in
api/secondary_sales_order.py - the doctype (Secondary Sales Order, owned by
fmcg_cp) whose own controller does nothing, so everything a real order needs
(channel partner, rate, item_template, territory) has to be derived here
instead of coming from the doctype for free."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate

from field_sales.api.secondary_sales_order import (
    create_secondary_sales_order,
    secondary_visit_order_prefill,
    submit_secondary_sales_order,
    update_secondary_sales_order,
)

REP = "ravi.tsm@demo.local"
PRICE_LIST = "Standard Selling"
LIST_RATE = 480.0


def ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.new_doc(doctype)
    doc.update(values)
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


class TestSecondarySalesOrderWrite(FrappeTestCase):
    @classmethod
    def _ensure_item(cls, item_code, item_name):
        if frappe.db.exists("Item", item_code):
            return item_code
        hsn = frappe.get_all("GST HSN Code", limit=1, pluck="name")
        cat = frappe.get_all("Item Category", limit=1, pluck="name")
        doc = frappe.new_doc("Item")
        doc.update({
            "item_code": item_code, "item_name": item_name,
            "item_group": "All Item Groups", "stock_uom": "Kg",
            "is_stock_item": 0, "is_sales_item": 1,
        })
        if hsn:
            doc.gst_hsn_code = hsn[0]
        if cat:
            doc.item_category = cat[0]
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return item_code

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = frappe.db.get_value(
            "Employee", {"user_id": REP, "status": "Active"}, "name"
        )

        cls.item = cls._ensure_item("FS-TEST-SSO-ITEM-001", "FS Test SSO Item")
        cls.unpriced_item = cls._ensure_item("FS-TEST-SSO-UNPRICED-ITEM", "FS Test SSO Unpriced Item")

        cls.channel_partner = ensure("Customer", "FS Test SSO Channel Partner", {
            "customer_name": "FS Test SSO Channel Partner",
            "customer_group": "Commercial", "territory": "Kolkata Area",
        })
        cls.customer = ensure("Customer", "FS Test SSO Secondary Customer", {
            "customer_name": "FS Test SSO Secondary Customer",
            "customer_group": "Commercial", "territory": "Kolkata Area",
        })
        frappe.db.set_value("Customer", cls.customer, {
            "customer_level": "Secondary",
            "custom_channel_partner": cls.channel_partner,
            "default_price_list": PRICE_LIST,
        })

        # CP Warehouse autonames as CP-WAR-{warehouse_name} - ensure() checking
        # existence by the raw name it was given would never match that.
        cls.warehouse = frappe.db.get_value("CP Warehouse", {"warehouse_name": "FS Test CP Warehouse"}, "name")
        if not cls.warehouse:
            cls.warehouse = ensure("CP Warehouse", "FS Test CP Warehouse", {
                "warehouse_name": "FS Test CP Warehouse",
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
        return doc.name

    def _cleanup(self):
        for name in frappe.get_all(
            "Secondary Sales Order", {"customer": self.customer}, pluck="name"
        ):
            doc = frappe.get_doc("Secondary Sales Order", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Secondary Sales Order", name, force=True, ignore_permissions=True)

    def _payload(self, rate=None, **overrides):
        payload = {
            "customer": self.customer,
            "set_warehouse": self.warehouse,
            "transaction_date": nowdate(),
            "items": [{
                "item_code": self.item, "qty": 10, "uom": "Kg",
                "rate": rate if rate is not None else 1,
            }],
        }
        payload.update(overrides)
        return payload

    # ------------------------------------------------------------ create

    def test_create_returns_a_draft(self):
        result = create_secondary_sales_order(**self._payload())
        self.assertTrue(result["name"])
        self.assertEqual(result["docstatus"], 0)

    def test_a_client_supplied_rate_is_not_stored(self):
        result = create_secondary_sales_order(**self._payload(rate=1))
        doc = frappe.get_doc("Secondary Sales Order", result["name"])
        self.assertEqual(flt(doc.items[0].rate, 2), LIST_RATE)
        self.assertNotEqual(flt(doc.items[0].rate, 2), 1.0)

    def test_amount_is_computed_from_the_resolved_rate(self):
        result = create_secondary_sales_order(**self._payload(rate=1))
        doc = frappe.get_doc("Secondary Sales Order", result["name"])
        self.assertEqual(flt(doc.items[0].amount, 2), flt(LIST_RATE * 10, 2))

    def test_item_template_is_derived_not_left_blank(self):
        """item_template is a mandatory field on Secondary Sales Order Item
        that nothing in the payload ever sets - without deriving it, insert
        would fail outright."""
        result = create_secondary_sales_order(**self._payload())
        doc = frappe.get_doc("Secondary Sales Order", result["name"])
        self.assertTrue(doc.items[0].item_template)

    def test_channel_partner_is_derived_from_the_customer(self):
        result = create_secondary_sales_order(**self._payload(custom_channel_partner="bogus"))
        doc = frappe.get_doc("Secondary Sales Order", result["name"])
        self.assertEqual(doc.custom_channel_partner, self.channel_partner)
        self.assertEqual(doc.customer_level, "Secondary")

    def test_create_requires_a_customer(self):
        with self.assertRaises(frappe.ValidationError):
            create_secondary_sales_order(
                set_warehouse=self.warehouse, transaction_date=nowdate(),
                items=[{"item_code": self.item, "qty": 1, "uom": "Kg"}],
            )

    def test_a_customer_with_no_channel_partner_is_refused(self):
        lone = ensure("Customer", "FS Test SSO No Partner Customer", {
            "customer_name": "FS Test SSO No Partner Customer",
            "customer_group": "Commercial", "territory": "Kolkata Area",
        })
        frappe.db.set_value("Customer", lone, {"customer_level": "Secondary", "custom_channel_partner": None})
        with self.assertRaises(frappe.ValidationError):
            create_secondary_sales_order(**self._payload(customer=lone))

    # ------------------------------------------------------------ manual quote

    def test_a_manual_quote_is_used_only_when_no_price_exists(self):
        """quote_custom_rate/quoted_rate are a gap-filler, not an override -
        this item does have a real price, so the quote is ignored."""
        result = create_secondary_sales_order(**self._payload(
            items=[{
                "item_code": self.item, "qty": 10, "uom": "Kg",
                "quote_custom_rate": 1, "quoted_rate": 1,
            }],
        ))
        doc = frappe.get_doc("Secondary Sales Order", result["name"])
        self.assertEqual(flt(doc.items[0].rate, 2), LIST_RATE)

    def test_a_manual_quote_fills_a_genuine_price_gap(self):
        result = create_secondary_sales_order(**self._payload(
            items=[{
                "item_code": self.unpriced_item, "qty": 5, "uom": "Kg",
                "quote_custom_rate": 1, "quoted_rate": 99,
            }],
        ))
        doc = frappe.get_doc("Secondary Sales Order", result["name"])
        self.assertEqual(flt(doc.items[0].rate, 2), 99.0)
        self.assertEqual(flt(doc.items[0].amount, 2), 495.0)

    def test_an_unpriced_item_without_a_quote_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            create_secondary_sales_order(**self._payload(
                items=[{"item_code": self.unpriced_item, "qty": 5, "uom": "Kg"}],
            ))

    # ------------------------------------------------------------ update / submit

    def test_update_edits_a_draft(self):
        name = create_secondary_sales_order(**self._payload())["name"]
        update_secondary_sales_order(name, remarks="Second pass")
        doc = frappe.get_doc("Secondary Sales Order", name)
        self.assertEqual(doc.remarks, "Second pass")

    def test_update_refuses_a_submitted_order(self):
        name = create_secondary_sales_order(**self._payload())["name"]
        submit_secondary_sales_order(name)
        with self.assertRaises(frappe.ValidationError):
            update_secondary_sales_order(name, remarks="too late")

    def test_submit_moves_docstatus_to_one(self):
        name = create_secondary_sales_order(**self._payload())["name"]
        result = submit_secondary_sales_order(name)
        self.assertEqual(result["docstatus"], 1)


class TestSecondaryVisitConversion(FrappeTestCase):
    """secondary_visit_order_prefill - the Channel Partner order side of the
    same feature as field_sales.api.catalog.visit_order_prefill: a Secondary
    customer's visit starts a pre-filled Channel Partner order form, read
    only, nothing created until the rep saves it themselves."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = frappe.db.get_value("Employee", {"user_id": REP, "status": "Active"}, "name")
        hsn = frappe.get_all("GST HSN Code", limit=1, pluck="name")
        cat = frappe.get_all("Item Category", limit=1, pluck="name")
        cls.item = "FS-TEST-SVC-ITEM"
        if not frappe.db.exists("Item", cls.item):
            doc = frappe.new_doc("Item")
            doc.update({
                "item_code": cls.item, "item_name": "FS Test Secondary Visit Conversion Item",
                "item_group": "All Item Groups", "stock_uom": "Kg",
                "is_stock_item": 0, "is_sales_item": 1,
                "gst_hsn_code": hsn[0] if hsn else None,
                "item_category": cat[0] if cat else None,
            })
            doc.flags.ignore_mandatory = True
            doc.insert(ignore_permissions=True)
        cls.channel_partner = ensure("Customer", "FS Test SVC Channel Partner", {
            "customer_name": "FS Test SVC Channel Partner",
            "customer_group": "Commercial", "territory": "Kolkata Area",
        })
        cls.secondary_customer = ensure("Customer", "FS Test SVC Secondary Customer", {
            "customer_name": "FS Test SVC Secondary Customer",
            "customer_group": "Commercial", "territory": "Kolkata Area",
        })
        frappe.db.set_value("Customer", cls.secondary_customer, {
            "customer_level": "Secondary",
            "custom_channel_partner": cls.channel_partner,
            "default_price_list": PRICE_LIST,
        })
        cls.primary_customer = ensure("Customer", "FS Test SVC Primary Customer", {
            "customer_name": "FS Test SVC Primary Customer",
            "customer_group": "Commercial", "territory": "Kolkata Area",
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
        for name in frappe.get_all("Secondary Sales Order", {"customer": self.secondary_customer}, pluck="name"):
            doc = frappe.get_doc("Secondary Sales Order", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Secondary Sales Order", name, force=True, ignore_permissions=True)
        for customer in (self.secondary_customer, self.primary_customer):
            for name in frappe.get_all("Field Visit", {"customer": customer}, pluck="name"):
                if frappe.db.get_value("Field Visit", name, "docstatus") == 1:
                    frappe.db.set_value("Field Visit", name, "docstatus", 0)
                frappe.delete_doc("Field Visit", name, force=True, ignore_permissions=True)

    def _visit(self, customer, docstatus=1, order_status="With Order", pitched_items=None):
        doc = frappe.new_doc("Field Visit")
        doc.update({
            "party_type": "Customer", "customer": customer, "visit_date": nowdate(),
            "order_status": order_status, "sales_person": self.employee,
        })
        for row in pitched_items or [{"item_code": self.item, "qty": 4, "uom": "Kg"}]:
            doc.append("pitched_items", row)
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        if docstatus == 1:
            frappe.db.set_value("Field Visit", doc.name, "docstatus", 1)
            doc.reload()
        return doc

    def test_prefill_returns_customer_and_channel_partner(self):
        visit = self._visit(self.secondary_customer)
        result = secondary_visit_order_prefill(visit.name)
        self.assertEqual(result["customer"], self.secondary_customer)
        self.assertEqual(result["custom_channel_partner"], self.channel_partner)
        self.assertEqual(result["fs_field_visit"], visit.name)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["rate"], LIST_RATE)

    def test_prefill_creates_nothing(self):
        visit = self._visit(self.secondary_customer)
        secondary_visit_order_prefill(visit.name)
        self.assertFalse(frappe.db.exists("Secondary Sales Order", {"fs_field_visit": visit.name}))

    def test_prefill_refuses_a_primary_customer(self):
        """The mirror image of catalog.py's visit_order_prefill refusing a
        Secondary customer - a Primary customer's order belongs on the
        Direct Customer flow, not here."""
        visit = self._visit(self.primary_customer)
        with self.assertRaises(frappe.ValidationError):
            secondary_visit_order_prefill(visit.name)

    def test_prefill_refuses_a_draft_visit(self):
        visit = self._visit(self.secondary_customer, docstatus=0)
        with self.assertRaises(frappe.ValidationError):
            secondary_visit_order_prefill(visit.name)

    def test_prefill_refuses_without_order(self):
        reason = ensure("Field Reason", "FS Test SVC Reason", {
            "reason": "FS Test SVC Reason", "applies_to": "Visit",
        })
        visit = frappe.new_doc("Field Visit")
        visit.update({
            "party_type": "Customer", "customer": self.secondary_customer, "visit_date": nowdate(),
            "order_status": "Without Order", "reason": reason, "sales_person": self.employee,
        })
        visit.append("pitched_items", {"item_code": self.item, "qty": 4, "uom": "Kg"})
        visit.flags.ignore_mandatory = True
        visit.insert(ignore_permissions=True)
        frappe.db.set_value("Field Visit", visit.name, "docstatus", 1)
        with self.assertRaises(frappe.ValidationError):
            secondary_visit_order_prefill(visit.name)

    def test_prefill_refuses_an_already_converted_visit(self):
        visit = self._visit(self.secondary_customer)
        result = secondary_visit_order_prefill(visit.name)
        create_secondary_sales_order(
            customer=result["customer"],
            set_warehouse=None,
            transaction_date=nowdate(),
            fs_field_visit=result["fs_field_visit"],
            items=[{"item_code": self.item, "qty": 4, "uom": "Kg"}],
        )
        with self.assertRaises(frappe.ValidationError):
            secondary_visit_order_prefill(visit.name)
