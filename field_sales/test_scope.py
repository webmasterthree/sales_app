# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for territory scoping.

The implementation this replaces built its scope by string-formatting
territory names into SQL. These tests pin the two things that has to mean:
the scope is correct, and it is expressed as filters that cannot be injected.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from field_sales import scope

TREE = [
    ("FS Test Zone", "All Territories", 1),
    ("FS Test Region", "FS Test Zone", 1),
    ("FS Test Area North", "FS Test Region", 0),
    ("FS Test Area South", "FS Test Region", 0),
    ("FS Test Other Region", "FS Test Zone", 1),
    ("FS Test Area Far", "FS Test Other Region", 0),
]


def ensure_territory(name: str, parent: str, is_group: int) -> None:
    if frappe.db.exists("Territory", name):
        return
    doc = frappe.new_doc("Territory")
    doc.update(
        {"territory_name": name, "parent_territory": parent, "is_group": is_group}
    )
    doc.insert(ignore_permissions=True)


def ensure_user(email: str, first_name: str) -> str:
    if not frappe.db.exists("User", email):
        doc = frappe.new_doc("User")
        doc.update(
            {
                "email": email,
                "first_name": first_name,
                "send_welcome_email": 0,
                "enabled": 1,
                "user_type": "System User",
            }
        )
        doc.insert(ignore_permissions=True)
    return email


class TestTerritoryScope(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for name, parent, is_group in TREE:
            ensure_territory(name, parent, is_group)
        cls.rep = ensure_user("fs.scope.rep@example.com", "Rep")
        cls.manager = ensure_user("fs.scope.manager@example.com", "Manager")
        cls.stranger = ensure_user("fs.scope.stranger@example.com", "Stranger")
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._clear_permissions()

    def tearDown(self):
        self._clear_permissions()
        frappe.set_user("Administrator")

    def _clear_permissions(self):
        for user in (self.rep, self.manager, self.stranger):
            for name in frappe.get_all(
                "User Permission", filters={"user": user}, pluck="name"
            ):
                frappe.delete_doc("User Permission", name, force=True, ignore_permissions=True)
        frappe.db.commit()

    def _grant(self, user: str, territory: str):
        doc = frappe.new_doc("User Permission")
        doc.update({"user": user, "allow": "Territory", "for_value": territory})
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

    # ------------------------------------------------------------ resolution

    def test_leaf_grant_returns_just_that_territory(self):
        self._grant(self.rep, "FS Test Area North")
        self.assertEqual(scope.effective_territories(self.rep), ["FS Test Area North"])

    def test_group_grant_includes_descendants(self):
        self._grant(self.manager, "FS Test Region")
        result = scope.effective_territories(self.manager)
        self.assertIn("FS Test Region", result)
        self.assertIn("FS Test Area North", result)
        self.assertIn("FS Test Area South", result)

    def test_scope_does_not_leak_sideways(self):
        """A grant on one branch must not expose a sibling branch."""
        self._grant(self.manager, "FS Test Region")
        result = scope.effective_territories(self.manager)
        self.assertNotIn("FS Test Area Far", result)
        self.assertNotIn("FS Test Other Region", result)

    def test_no_grant_and_no_employee_is_empty(self):
        self.assertEqual(scope.effective_territories(self.stranger), [])

    def test_multiple_grants_are_unioned(self):
        self._grant(self.manager, "FS Test Area North")
        self._grant(self.manager, "FS Test Area Far")
        result = scope.effective_territories(self.manager)
        self.assertIn("FS Test Area North", result)
        self.assertIn("FS Test Area Far", result)
        self.assertNotIn("FS Test Area South", result)

    def test_stale_grant_does_not_break_resolution(self):
        """A grant pointing at a deleted territory must narrow, not explode."""
        self._grant(self.rep, "FS Test Area North")
        frappe.db.set_value(
            "User Permission",
            frappe.get_all("User Permission", {"user": self.rep}, pluck="name")[0],
            "for_value",
            "FS Test Territory That Does Not Exist",
        )
        result = scope.effective_territories(self.rep)
        self.assertEqual(result, ["FS Test Territory That Does Not Exist"])

    # ------------------------------------------------------------ filters

    def test_filter_is_a_dict_not_sql(self):
        """The whole point: no SQL fragments leave this module."""
        self._grant(self.rep, "FS Test Area North")
        f = scope.territory_filter(self.rep)
        self.assertIsInstance(f, dict)
        self.assertEqual(f["area"][0], "in")
        self.assertIsInstance(f["area"][1], list)

    def test_scoped_user_with_no_territory_sees_nothing(self):
        """Failing closed matters more than failing loudly."""
        f = scope.territory_filter(self.stranger)
        self.assertEqual(f, {"area": ["in", []]})

    def test_injection_in_a_territory_name_stays_data(self):
        """A territory named with SQL must not become SQL."""
        nasty = "FS Test '); drop table `tabUser`; --"
        ensure_territory(nasty, "FS Test Region", 0)
        self._grant(self.rep, nasty)
        try:
            f = scope.territory_filter(self.rep)
            self.assertIn(nasty, f["area"][1])

            # and it survives a real query as a plain value
            rows = frappe.get_all(
                "Territory",
                filters={"name": ["in", f["area"][1]]},
                pluck="name",
                ignore_permissions=True,
            )
            self.assertIn(nasty, rows)
            self.assertTrue(frappe.db.exists("DocType", "User"), "tabUser survived")
        finally:
            frappe.delete_doc("Territory", nasty, force=True, ignore_permissions=True)
            frappe.db.commit()

    def test_mine_only_adds_an_owner_filter(self):
        self._grant(self.rep, "FS Test Area North")
        f = scope.scoped_filters(self.rep, mine_only=True)
        self.assertIn("area", f)
        self.assertIn("created_by_emp", f)

    def test_administrator_is_unrestricted(self):
        self.assertTrue(scope.has_unrestricted_scope("Administrator"))
        self.assertEqual(scope.territory_filter("Administrator"), {})

    def test_custom_fieldname_is_respected(self):
        self._grant(self.rep, "FS Test Area North")
        f = scope.territory_filter(self.rep, fieldname="territory")
        self.assertIn("territory", f)

    def test_resolve_leaf_territory_keeps_a_real_leaf(self):
        self.assertEqual(
            scope.resolve_leaf_territory("FS Test Area North"), "FS Test Area North"
        )

    def test_resolve_leaf_territory_replaces_a_group(self):
        """The exact failure mode: Frappe pre-fills `territory` with the
        system default "All Territories" - a group - before validate() runs."""
        result = scope.resolve_leaf_territory("FS Test Zone", fallback_user=self.rep)
        self.assertNotEqual(result, "FS Test Zone")

    def test_resolve_leaf_territory_falls_back_to_the_employee(self):
        emp = frappe.db.get_value("Employee", {"user_id": self.rep}, "name")
        if emp:
            frappe.db.set_value("Employee", emp, "area", "FS Test Area South")
            result = scope.resolve_leaf_territory(None, fallback_user=self.rep)
            self.assertEqual(result, "FS Test Area South")

    def test_resolve_leaf_territory_handles_no_value_and_no_employee(self):
        result = scope.resolve_leaf_territory(None, fallback_user="Guest")
        self.assertIsNone(result)
