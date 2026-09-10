# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the generic comment thread capability (field_sales.api.comments)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from field_sales.api.comments import add_comment, comment_list
from field_sales.api.field_visit import create_visit

REP = "ravi.tsm@demo.local"
REP_TERRITORY = "Kolkata Area"

# A second demo user with none of the roles Field Visit grants read to
# (Sales Executive App / Sales Manager / System Manager - see its DocPerm
# rows), used to prove the permission check actually refuses someone rather
# than just being present. Every other detail endpoint in this app (e.g.
# api.field_visit.visit) gates on doc.check_permission("read") alone, with
# no doctype-level has_permission hook narrowing that further by territory -
# comments intentionally match that existing, app-wide convention rather
# than inventing a stricter model just for itself.
OUTSIDER = "test_comments_outsider@example.com"


def ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.new_doc(doctype)
    doc.update(values)
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


class TestComments(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = frappe.db.get_value("Customer", {}, "name")
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()

        if not frappe.db.exists("User", OUTSIDER):
            outsider = frappe.new_doc("User")
            outsider.update({
                "email": OUTSIDER,
                "first_name": "Comments Outsider",
                "send_welcome_email": 0,
            })
            # Deliberately no "Sales Executive App" (or any other) role that
            # Field Visit grants read to - this user should fail the same
            # ordinary doctype permission check any other endpoint would.
            outsider.flags.ignore_mandatory = True
            outsider.insert(ignore_permissions=True)

        # File the visit as the real rep, same as test_field_visit_write.py -
        # the endpoints refuse to work against a user with no Employee.
        frappe.set_user(REP)
        self.visit = create_visit(
            party_type="Customer",
            customer=self.customer,
            outlet_name="FS Comments Test Outlet",
            visit_date=nowdate(),
            territory=REP_TERRITORY,
            order_status="With Order",
        )["name"]

    def tearDown(self):
        frappe.set_user("Administrator")
        self._cleanup()
        frappe.db.rollback()

    def _cleanup(self):
        for name in frappe.get_all("Field Visit", {"outlet_name": "FS Comments Test Outlet"}, pluck="name"):
            doc = frappe.get_doc("Field Visit", name)
            if doc.docstatus == 1:
                doc.cancel()
            for comment in frappe.get_all(
                "Comment", {"reference_doctype": "Field Visit", "reference_name": name}, pluck="name"
            ):
                frappe.delete_doc("Comment", comment, force=True, ignore_permissions=True)
            frappe.delete_doc("Field Visit", name, force=True, ignore_permissions=True)

    # ------------------------------------------------------------ scope

    def test_an_unlisted_doctype_is_refused(self):
        frappe.set_user(REP)
        with self.assertRaises(frappe.ValidationError):
            comment_list("User", "Administrator")
        with self.assertRaises(frappe.ValidationError):
            add_comment("User", "Administrator", "hi")

    # ------------------------------------------------------------ read/write

    def test_comment_list_starts_empty(self):
        frappe.set_user(REP)
        self.assertEqual(comment_list("Field Visit", self.visit), [])

    def test_add_comment_then_read_it_back(self):
        frappe.set_user(REP)
        result = add_comment("Field Visit", self.visit, "Called the outlet, order confirmed.")
        self.assertEqual(result["content"], "Called the outlet, order confirmed.")
        self.assertEqual(result["comment_email"], REP)

        rows = comment_list("Field Visit", self.visit)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["content"], "Called the outlet, order confirmed.")

    def test_comments_come_back_oldest_first(self):
        frappe.set_user(REP)
        add_comment("Field Visit", self.visit, "First note")
        add_comment("Field Visit", self.visit, "Second note")
        rows = comment_list("Field Visit", self.visit)
        self.assertEqual([r["content"] for r in rows], ["First note", "Second note"])

    def test_blank_comment_is_refused(self):
        frappe.set_user(REP)
        with self.assertRaises(frappe.ValidationError):
            add_comment("Field Visit", self.visit, "   ")

    def test_add_comment_uses_frappes_native_comment_doctype(self):
        """Not a bespoke doctype - the same mechanism the desk timeline uses."""
        frappe.set_user(REP)
        result = add_comment("Field Visit", self.visit, "Native comment check")
        self.assertTrue(frappe.db.exists("Comment", result["name"]))
        row = frappe.db.get_value(
            "Comment", result["name"],
            ["reference_doctype", "reference_name", "comment_type"], as_dict=True,
        )
        self.assertEqual(row.reference_doctype, "Field Visit")
        self.assertEqual(row.reference_name, self.visit)
        self.assertEqual(row.comment_type, "Comment")

    # ------------------------------------------------------------ permission

    def test_a_user_without_the_role_cannot_read_or_write(self):
        frappe.set_user(REP)
        add_comment("Field Visit", self.visit, "Rep's own note")

        frappe.set_user(OUTSIDER)
        with self.assertRaises(frappe.PermissionError):
            comment_list("Field Visit", self.visit)
        with self.assertRaises(frappe.PermissionError):
            add_comment("Field Visit", self.visit, "Should never land")
