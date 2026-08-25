# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the request modules and the collateral library."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from field_sales.api.listing import paginated_list
from field_sales.api.requests import (
    COLLATERAL_CONFIG,
    COLLATERAL_LIBRARY_CONFIG,
    SAMPLE_CONFIG,
    collateral_library,
)

TERRITORY = "Kolkata Area"
OTHER_TERRITORY = "Pune Area"


class TestRequests(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = frappe.db.get_value("Customer", {}, "name")
        cls.employee = frappe.db.get_value(
            "Employee", {"user_id": "ravi.tsm@demo.local"}, "name"
        )
        cls.other_employee = frappe.db.get_value(
            "Employee", {"user_id": "priya.tsm@demo.local"}, "name"
        )
        cls.item = frappe.db.get_value("Item", {"is_sales_item": 1}, "name")
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()

    def tearDown(self):
        frappe.set_user("Administrator")
        self._cleanup()
        frappe.db.rollback()

    def _cleanup(self):
        for dt in ("Sample Request", "Collateral Request"):
            for name in frappe.get_all(dt, pluck="name"):
                doc = frappe.get_doc(dt, name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        for name in frappe.get_all(
            "Sales Collateral", {"collateral_name": ["like", "FS Test%"]}, pluck="name"
        ):
            frappe.delete_doc("Sales Collateral", name, force=True, ignore_permissions=True)

    # ------------------------------------------------------------ builders

    def _sample(self, territory=TERRITORY, employee=None, status=None, submit=False):
        doc = frappe.new_doc("Sample Request")
        doc.update({
            "request_date": nowdate(),
            "required_by": add_days(nowdate(), 5),
            "party_type": "Customer",
            "customer": self.customer,
            "sales_person": employee or self.employee,
            "territory": territory,
            "purpose": "Trial at the bakery",
        })
        doc.append("items", {"item_code": self.item, "qty": 3, "uom": "Kg"})
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        if status:
            frappe.db.set_value("Sample Request", doc.name, "status", status)
        if submit:
            doc.reload()
            doc.submit()
        return doc

    def _collateral_request(self, territory=TERRITORY):
        doc = frappe.new_doc("Collateral Request")
        doc.update({
            "request_date": nowdate(),
            "party_type": "Customer",
            "customer": self.customer,
            "sales_person": self.employee,
            "territory": territory,
        })
        doc.append("items", {"description": "Counter danglers", "qty": 20})
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return doc

    def _collateral(self, name, published=1, ctype="Leaflet"):
        doc = frappe.new_doc("Sales Collateral")
        doc.update({
            "collateral_name": name, "collateral_type": ctype,
            "published": published, "description": "A demo asset",
        })
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return doc

    def _list(self, config, **form):
        return paginated_list(config, form=form, user="Administrator")

    # ------------------------------------------------------------ sample requests

    def test_a_sample_request_saves(self):
        doc = self._sample()
        self.assertTrue(doc.name.startswith("SR-"))
        self.assertEqual(doc.status, "Pending")
        self.assertEqual(len(doc.items), 1)

    def test_sample_request_requires_items(self):
        doc = frappe.new_doc("Sample Request")
        doc.update({
            "request_date": nowdate(), "sales_person": self.employee,
            "territory": TERRITORY,
        })
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)

    def test_sample_list_returns_the_request(self):
        doc = self._sample()
        result = self._list(SAMPLE_CONFIG)
        self.assertIn(doc.name, [r["name"] for r in result["records"]])

    def test_sample_list_status_tabs(self):
        self._sample(status="Pending")
        approved = self._sample(status="Approved")
        result = self._list(SAMPLE_CONFIG, tab="approved")
        names = [r["name"] for r in result["records"]]
        self.assertIn(approved.name, names)
        self.assertEqual(result["total_count"], 1)

    def test_sample_list_draft_and_submitted_tabs(self):
        draft = self._sample()
        submitted = self._sample(submit=True)
        d = self._list(SAMPLE_CONFIG, tab="draft")
        s = self._list(SAMPLE_CONFIG, tab="submitted")
        self.assertIn(draft.name, [r["name"] for r in d["records"]])
        self.assertIn(submitted.name, [r["name"] for r in s["records"]])

    def test_sample_list_search_is_parameterised(self):
        self._sample()
        hit = self._list(SAMPLE_CONFIG, search_text="SR-")
        self.assertGreaterEqual(hit["total_count"], 1)
        inject = self._list(
            SAMPLE_CONFIG, search_text='" or 1=1 or name LIKE "'
        )
        self.assertEqual(inject["total_count"], 0)

    def test_sample_list_is_territory_scoped(self):
        mine = self._sample(territory=TERRITORY)
        theirs = self._sample(territory=OTHER_TERRITORY, employee=self.other_employee)

        frappe.set_user("ravi.tsm@demo.local")
        try:
            result = paginated_list(SAMPLE_CONFIG, form={}, user="ravi.tsm@demo.local")
            names = [r["name"] for r in result["records"]]
            self.assertIn(mine.name, names)
            self.assertNotIn(theirs.name, names, "a rep saw another territory's request")
        finally:
            frappe.set_user("Administrator")

    def test_sample_list_mine_toggle(self):
        mine = self._sample(employee=self.employee)
        theirs = self._sample(employee=self.other_employee)
        result = paginated_list(
            SAMPLE_CONFIG, form={"is_self": 1}, user="ravi.tsm@demo.local"
        )
        names = [r["name"] for r in result["records"]]
        self.assertIn(mine.name, names)
        self.assertNotIn(theirs.name, names)

    # ------------------------------------------------------------ collateral requests

    def test_a_collateral_request_saves(self):
        doc = self._collateral_request()
        self.assertTrue(doc.name.startswith("CR-"))
        self.assertEqual(doc.items[0].qty, 20)

    def test_collateral_request_allows_a_free_text_item(self):
        """Not everything a rep asks for is in the library."""
        doc = self._collateral_request()
        self.assertIsNone(doc.items[0].collateral)
        self.assertEqual(doc.items[0].description, "Counter danglers")

    def test_collateral_request_list(self):
        doc = self._collateral_request()
        result = self._list(COLLATERAL_CONFIG)
        self.assertIn(doc.name, [r["name"] for r in result["records"]])

    def test_the_two_request_lists_do_not_bleed_into_each_other(self):
        sample = self._sample()
        collateral = self._collateral_request()
        s = [r["name"] for r in self._list(SAMPLE_CONFIG)["records"]]
        c = [r["name"] for r in self._list(COLLATERAL_CONFIG)["records"]]
        self.assertIn(sample.name, s)
        self.assertNotIn(collateral.name, s)
        self.assertIn(collateral.name, c)
        self.assertNotIn(sample.name, c)

    # ------------------------------------------------------------ collateral library

    def test_library_shows_only_published_collateral(self):
        published = self._collateral("FS Test Published", published=1)
        draft = self._collateral("FS Test Unpublished", published=0)

        frappe.form_dict = frappe._dict({})
        result = collateral_library()
        names = [r["name"] for r in result["records"]]
        self.assertIn(published.name, names)
        self.assertNotIn(draft.name, names, "unpublished collateral reached the app")

    def test_library_filters_by_type(self):
        self._collateral("FS Test Leaflet", ctype="Leaflet")
        self._collateral("FS Test Poster", ctype="Poster")
        result = self._list(COLLATERAL_LIBRARY_CONFIG, collateral_type="Poster")
        names = [r["collateral_name"] for r in result["records"]]
        self.assertIn("FS Test Poster", names)
        self.assertNotIn("FS Test Leaflet", names)

    def test_library_is_not_territory_scoped(self):
        """Collateral is company-wide; scoping it by territory would hide it."""
        self.assertIsNone(COLLATERAL_LIBRARY_CONFIG.territory_field)
