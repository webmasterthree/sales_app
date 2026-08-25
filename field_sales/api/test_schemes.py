# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the schemes view."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from field_sales.api.schemes import scheme_list


def ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.new_doc(doctype)
    doc.update(values)
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


class TestSchemes(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()
        frappe.form_dict = frappe._dict({})

    def tearDown(self):
        self._cleanup()
        frappe.form_dict = frappe._dict({})
        frappe.db.rollback()

    def _cleanup(self):
        for name in frappe.get_all(
            "Pricing Rule", {"title": ["like", "FS Scheme Test%"]}, pluck="name"
        ):
            frappe.delete_doc("Pricing Rule", name, force=True, ignore_permissions=True)

    def _scheme(self, title, valid_upto=None, rate_or_discount="Discount Percentage",
               selling=1, disable=0):
        doc = frappe.new_doc("Pricing Rule")
        doc.update({
            "title": title, "apply_on": "Item Code",
            "selling": selling, "buying": 0 if selling else 1,
            "price_or_product_discount": "Price",
            "rate_or_discount": rate_or_discount,
            "discount_percentage": 10, "disable": disable,
        })
        if valid_upto:
            # valid_from must not be after valid_upto
            doc.valid_from = add_days(valid_upto, -60)
            doc.valid_upto = valid_upto
        item = frappe.db.get_value("Item", {}, "name")
        if item:
            doc.append("items", {"item_code": item})
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return doc

    def test_a_discount_rule_appears_as_a_scheme(self):
        self._scheme("FS Scheme Test Monsoon", valid_upto=add_days(nowdate(), 30))
        result = scheme_list()
        titles = [r["title"] for r in result["records"]]
        self.assertIn("FS Scheme Test Monsoon", titles)

    def test_a_rate_override_rule_is_not_a_scheme(self):
        """Only discount-percentage rules are schemes; a fixed-rate rule is not."""
        self._scheme("FS Scheme Test FixedRate", rate_or_discount="Rate",
                     valid_upto=add_days(nowdate(), 30))
        result = scheme_list()
        titles = [r["title"] for r in result["records"]]
        self.assertNotIn("FS Scheme Test FixedRate", titles)

    def test_a_buying_rule_is_not_a_scheme(self):
        self._scheme("FS Scheme Test Buying", selling=0,
                     valid_upto=add_days(nowdate(), 30))
        result = scheme_list()
        titles = [r["title"] for r in result["records"]]
        self.assertNotIn("FS Scheme Test Buying", titles)

    def test_a_disabled_rule_is_not_a_scheme(self):
        self._scheme("FS Scheme Test Disabled", disable=1,
                     valid_upto=add_days(nowdate(), 30))
        result = scheme_list()
        titles = [r["title"] for r in result["records"]]
        self.assertNotIn("FS Scheme Test Disabled", titles)

    def test_an_expired_scheme_is_hidden_by_default(self):
        self._scheme("FS Scheme Test Expired", valid_upto=add_days(nowdate(), -5))
        result = scheme_list()
        titles = [r["title"] for r in result["records"]]
        self.assertNotIn("FS Scheme Test Expired", titles)

    def test_include_expired_shows_it(self):
        self._scheme("FS Scheme Test Expired2", valid_upto=add_days(nowdate(), -5))
        frappe.form_dict = frappe._dict({"include_expired": 1})
        result = scheme_list()
        titles = [r["title"] for r in result["records"]]
        self.assertIn("FS Scheme Test Expired2", titles)

    def test_search_is_parameterised(self):
        self._scheme("FS Scheme Test Searchable", valid_upto=add_days(nowdate(), 30))
        frappe.form_dict = frappe._dict({"search_text": '" or 1=1 or title LIKE "'})
        result = scheme_list()
        self.assertEqual(result["total_count"], 0)
