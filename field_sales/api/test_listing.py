# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the shared list endpoint.

The point of this module is that user input never becomes SQL text. These
tests push the payloads that worked against the implementation it replaces -
quote-breaking search terms, an injected ORDER BY, undeclared filter
parameters - and assert both that nothing executes and that the data is still
correct.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from field_sales.api.listing import ListConfig, paginated_list

TERRITORY = "FS List Test Area"
OTHER_TERRITORY = "FS List Test Other"


def ensure_territory(name: str) -> str:
    if not frappe.db.exists("Territory", name):
        doc = frappe.new_doc("Territory")
        doc.update({"territory_name": name, "parent_territory": "All Territories", "is_group": 0})
        doc.insert(ignore_permissions=True)
    return name


class TestListing(FrappeTestCase):
    """Uses Note as a neutral carrier so the tests do not depend on the
    field-sales doctypes existing yet."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_territory(TERRITORY)
        ensure_territory(OTHER_TERRITORY)
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()
        self.titles = [
            "Alpha visit report",
            "Beta visit report",
            "Gamma order summary",
            "O'Brien bakery",  # a legitimate apostrophe, not an attack
        ]
        for t in self.titles:
            doc = frappe.new_doc("Note")
            doc.update({"title": t, "public": 1})
            doc.insert(ignore_permissions=True)

        self.config = ListConfig(
            doctype="Note",
            fields=["name", "title"],
            search_fields=["title"],
            filter_fields={"public": "public"},
            territory_field=None,   # Note has no territory
            owner_field=None,
            default_order="title asc",
            sortable_fields=["name", "title"],
        )

    def tearDown(self):
        self._cleanup()
        frappe.db.rollback()

    def _cleanup(self):
        for name in frappe.get_all("Note", pluck="name"):
            frappe.delete_doc("Note", name, force=True, ignore_permissions=True)

    def _list(self, **form):
        return paginated_list(self.config, form=form)

    # ------------------------------------------------------------ basics

    def test_lists_everything_by_default(self):
        result = self._list()
        self.assertEqual(result["total_count"], len(self.titles))
        self.assertEqual(len(result["records"]), len(self.titles))

    def test_search_matches_a_substring(self):
        result = self._list(search_text="visit")
        titles = [r["title"] for r in result["records"]]
        self.assertEqual(len(titles), 2)
        self.assertTrue(all("visit" in t for t in titles))

    def test_search_is_reported_in_the_count(self):
        result = self._list(search_text="visit")
        self.assertEqual(result["total_count"], 2)
        self.assertEqual(result["page_count"], 1)

    # ------------------------------------------------------------ injection

    def test_working_bypass_payload_is_neutralised(self):
        """Verified to return every row against the old string-formatted query.

        The payload closes the LIKE and reopens one so the statement stays well
        formed:  AND (title LIKE "%" or 1=1 or title LIKE "%")
        A clumsier payload only causes a syntax error, which proves the value is
        parsed as SQL but leaks nothing on its own - so this is the shape worth
        pinning.
        """
        payload = '" or 1=1 or title LIKE "'
        result = self._list(search_text=payload)
        self.assertEqual(
            result["total_count"], 0,
            "an injected OR matched rows - the value reached SQL as code",
        )
        self.assertEqual(frappe.db.count("Note"), len(self.titles))

    def test_subquery_read_is_neutralised(self):
        """The same trick reading a different table entirely."""
        payload = '" or (select count(*) from `tabUser`) > 0 or title LIKE "'
        result = self._list(search_text=payload)
        self.assertEqual(result["total_count"], 0)

    def test_malformed_payload_neither_errors_nor_matches(self):
        result = self._list(search_text='%" or 1=1 -- ')
        self.assertEqual(result["total_count"], 0)

    def test_drop_attempt_is_treated_as_data(self):
        result = self._list(search_text="'); drop table `tabNote`; --")
        self.assertEqual(result["total_count"], 0)
        self.assertTrue(frappe.db.exists("DocType", "Note"))
        self.assertEqual(frappe.db.count("Note"), len(self.titles))

    def test_a_legitimate_apostrophe_still_matches(self):
        """Escaping must not break real data - O'Brien is a customer name."""
        result = self._list(search_text="O'Brien")
        self.assertEqual(result["total_count"], 1)
        self.assertEqual(result["records"][0]["title"], "O'Brien bakery")

    def test_injected_order_by_falls_back_to_the_default(self):
        """order_by is the one clause Frappe interpolates rather than binds."""
        result = self._list(order_by="title asc, (select 1) --")
        titles = [r["title"] for r in result["records"]]
        self.assertEqual(titles, sorted(titles))
        self.assertEqual(len(titles), len(self.titles))

    def test_order_by_an_undeclared_field_is_ignored(self):
        result = self._list(order_by="owner desc")
        titles = [r["title"] for r in result["records"]]
        self.assertEqual(titles, sorted(titles), "fell back to the declared default")

    def test_a_declared_sort_is_honoured(self):
        result = self._list(order_by="title desc")
        titles = [r["title"] for r in result["records"]]
        self.assertEqual(titles, sorted(titles, reverse=True))

    def test_undeclared_filters_are_ignored(self):
        """An attacker adding ?owner=... must not narrow or widen the set."""
        result = self._list(owner="nobody@example.com")
        self.assertEqual(result["total_count"], len(self.titles))

    def test_declared_filter_is_applied(self):
        frappe.db.set_value(
            "Note", frappe.get_all("Note", {"title": "Alpha visit report"}, pluck="name")[0],
            "public", 0,
        )
        result = self._list(public=1)
        self.assertEqual(result["total_count"], len(self.titles) - 1)

    # ------------------------------------------------------------ pagination

    def test_pagination_slices_and_counts(self):
        first = self._list(limit=2, current_page=1)
        second = self._list(limit=2, current_page=2)
        self.assertEqual(len(first["records"]), 2)
        self.assertEqual(len(second["records"]), 2)
        self.assertEqual(first["total_count"], len(self.titles))
        self.assertEqual(first["page_count"], 2)
        self.assertNotEqual(
            [r["name"] for r in first["records"]],
            [r["name"] for r in second["records"]],
        )

    def test_page_size_is_capped(self):
        result = self._list(limit=100000)
        self.assertLessEqual(result["page_size"], 100)

    def test_nonsense_pagination_is_coerced(self):
        result = self._list(limit="; drop table x", current_page="-5")
        self.assertEqual(result["current_page"], 1)
        self.assertGreaterEqual(result["page_size"], 1)

    # ------------------------------------------------------------ permission

    def test_read_permission_is_enforced(self):
        config = ListConfig(
            doctype="User Permission",
            fields=["name"],
            territory_field=None,
            owner_field=None,
        )
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.PermissionError):
                paginated_list(config, form={})
        finally:
            frappe.set_user("Administrator")

    # ------------------------------------------------------------ base_filters

    def test_base_filters_are_always_applied(self):
        """e.g. narrowing Pricing Rule down to just discount schemes."""
        config = ListConfig(
            doctype="Note", fields=["name", "title"],
            territory_field=None, owner_field=None,
            base_filters={"public": 1},
        )
        frappe.db.set_value(
            "Note", frappe.get_all("Note", {"title": "Alpha visit report"}, pluck="name")[0],
            "public", 0,
        )
        result = paginated_list(config, form={})
        self.assertEqual(result["total_count"], len(self.titles) - 1)

    def test_base_filters_cannot_be_overridden_by_an_undeclared_param(self):
        config = ListConfig(
            doctype="Note", fields=["name", "title"],
            territory_field=None, owner_field=None,
            base_filters={"public": 1},
        )
        frappe.db.set_value(
            "Note", frappe.get_all("Note", {"title": "Alpha visit report"}, pluck="name")[0],
            "public", 0,
        )
        result = paginated_list(config, form={"public": 0})
        self.assertEqual(
            result["total_count"], len(self.titles) - 1,
            "an undeclared query parameter overrode a base filter",
        )
