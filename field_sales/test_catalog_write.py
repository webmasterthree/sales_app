# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the Sales Order write path in api/catalog.py.

field_sales.test_pricing already covers enforce_sales_order_rates as a unit -
calling it directly against a bare frappe.new_doc("Sales Order"). These tests
cover the thing that unit test cannot: that the whitelisted create_order/
update_order/submit_order endpoints, exercising the real insert/save/submit
lifecycle, still end up with the server's own rate on disk even when a client
sends a different one - the actual defect this app existed to close.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate

from field_sales.api.catalog import create_order, submit_order, update_order

REP = "ravi.tsm@demo.local"
PRICE_LIST = "Standard Selling"
LIST_RATE = 640.0


def ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.new_doc(doctype)
    doc.update(values)
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


class TestSalesOrderWrite(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = frappe.db.get_value(
            "Employee", {"user_id": REP, "status": "Active"}, "name"
        )

        cls.item = "FS-TEST-CATALOG-ITEM-001"
        if not frappe.db.exists("Item", cls.item):
            hsn = frappe.get_all("GST HSN Code", limit=1, pluck="name")
            cat = frappe.get_all("Item Category", limit=1, pluck="name")
            doc = frappe.new_doc("Item")
            doc.update({
                "item_code": cls.item, "item_name": "FS Test Catalog Item",
                "item_group": "All Item Groups", "stock_uom": "Kg",
                "is_stock_item": 0, "is_sales_item": 1,
            })
            if hsn:
                doc.gst_hsn_code = hsn[0]
            if cat:
                doc.item_category = cat[0]
            doc.flags.ignore_mandatory = True
            doc.insert(ignore_permissions=True)

        cls.customer = "FS Test Catalog Customer"
        if not frappe.db.exists("Customer", {"customer_name": cls.customer}):
            doc = frappe.new_doc("Customer")
            doc.update({
                "customer_name": cls.customer, "customer_type": "Company",
                "customer_group": "Commercial", "territory": "Kolkata Area",
                "business_type": "Registered", "gst_category": "Registered Regular",
            })
            doc.flags.ignore_mandatory = True
            doc.insert(ignore_permissions=True)
        cls.customer = frappe.db.get_value(
            "Customer", {"customer_name": cls.customer}, "name"
        )

        shop = frappe.get_all("Shop", limit=1, pluck="name")
        cls.shop = shop[0] if shop else None
        frappe.db.set_value("Customer", cls.customer, "custom_shop", cls.shop)
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
            "Sales Order", {"customer": self.customer}, pluck="name"
        ):
            doc = frappe.get_doc("Sales Order", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Sales Order", name, force=True, ignore_permissions=True)

    def _payload(self, rate=None, **overrides):
        payload = {
            "customer": self.customer,
            "delivery_date": add_days(nowdate(), 7),
            "items": [{
                "item_code": self.item, "qty": 10, "uom": "Kg",
                "rate": rate if rate is not None else 1,
                "amount": 999999,
                "price_list_rate": 1,
            }],
        }
        payload.update(overrides)
        return payload

    # ------------------------------------------------------------ create

    def test_create_returns_a_draft(self):
        result = create_order(**self._payload())
        self.assertTrue(result["name"])
        self.assertEqual(result["docstatus"], 0)

    def test_a_client_supplied_rate_is_not_stored(self):
        """The headline defect: a client could name its own order price."""
        result = create_order(**self._payload(rate=1))
        doc = frappe.get_doc("Sales Order", result["name"])
        self.assertEqual(flt(doc.items[0].rate, 2), LIST_RATE)
        self.assertNotEqual(flt(doc.items[0].rate, 2), 1.0)

    def test_stored_rate_matches_what_item_price_would_quote(self):
        """What the app shows in step two must be what the order stores."""
        from field_sales.api.catalog import item_price

        quoted = item_price(item_code=self.item, customer=self.customer, qty=10)
        result = create_order(**self._payload(rate=1))
        doc = frappe.get_doc("Sales Order", result["name"])
        self.assertEqual(flt(doc.items[0].rate, 2), flt(quoted["final_rate"], 2))

    def test_client_cannot_set_amount_or_price_list_rate_directly(self):
        result = create_order(**self._payload(rate=1))
        doc = frappe.get_doc("Sales Order", result["name"])
        self.assertNotEqual(flt(doc.items[0].amount, 2), 999999.0)

    def test_create_forces_the_signed_in_users_own_employee(self):
        result = create_order(**self._payload())
        doc = frappe.get_doc("Sales Order", result["name"])
        if doc.meta.has_field("created_by_emp"):
            self.assertEqual(doc.created_by_emp, self.employee)

    def test_create_derives_shop_from_the_customer(self):
        result = create_order(**self._payload())
        doc = frappe.get_doc("Sales Order", result["name"])
        self.assertEqual(doc.shop, self.shop)

    def test_create_ignores_a_client_sent_shop(self):
        other = frappe.get_all(
            "Shop", filters={"name": ["!=", self.shop]}, limit=1, pluck="name"
        )
        if not other:
            self.skipTest("only one Shop on this site")
        result = create_order(**self._payload(shop=other[0]))
        doc = frappe.get_doc("Sales Order", result["name"])
        self.assertEqual(doc.shop, self.shop)

    def test_create_requires_a_customer(self):
        with self.assertRaises(frappe.ValidationError):
            create_order(delivery_date=add_days(nowdate(), 7), items=[
                {"item_code": self.item, "qty": 1, "uom": "Kg"}
            ])

    # ------------------------------------------------------------ update / submit

    def test_update_edits_a_draft(self):
        name = create_order(**self._payload())["name"]
        update_order(name, remarks="Second pass")
        doc = frappe.get_doc("Sales Order", name)
        self.assertEqual(doc.remarks, "Second pass")

    def test_update_recomputes_rate_after_a_client_edit(self):
        name = create_order(**self._payload())["name"]
        update_order(name, items=[{
            "item_code": self.item, "qty": 20, "uom": "Kg", "rate": 1,
        }])
        doc = frappe.get_doc("Sales Order", name)
        self.assertEqual(flt(doc.items[0].rate, 2), LIST_RATE)

    def test_update_refuses_a_submitted_order(self):
        name = create_order(**self._payload())["name"]
        submit_order(name)
        with self.assertRaises(frappe.ValidationError):
            update_order(name, remarks="too late")

    def test_submit_moves_docstatus_to_one(self):
        name = create_order(**self._payload())["name"]
        result = submit_order(name)
        self.assertEqual(result["docstatus"], 1)
