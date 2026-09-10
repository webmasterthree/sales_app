# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for who gets notified on a Field Visit / Sales Order update: the
rep's manager when the rep acts, the rep when someone else does."""

import frappe
from frappe.tests.utils import FrappeTestCase

from field_sales import notify

REP = "fs.notify.rep@example.com"
MANAGER = "fs.notify.manager@example.com"
COMPANY = None  # resolved in setUpClass


def _ensure_user(email):
    if not frappe.db.exists("User", email):
        user = frappe.new_doc("User")
        user.update({
            "email": email, "first_name": email.split("@")[0],
            "send_welcome_email": 0, "role_profile_name": None,
        })
        user.insert(ignore_permissions=True)
    return email


def _ensure_employee(name, user_id, reports_to=None):
    if frappe.db.exists("Employee", {"user_id": user_id}):
        emp_name = frappe.db.get_value("Employee", {"user_id": user_id}, "name")
        if reports_to:
            frappe.db.set_value("Employee", emp_name, "reports_to", reports_to)
        return emp_name
    emp = frappe.new_doc("Employee")
    emp.update({
        "employee_name": name, "user_id": user_id, "status": "Active",
        "company": frappe.defaults.get_global_default("company"),
        "date_of_joining": frappe.utils.nowdate(), "date_of_birth": "1990-01-01",
        "gender": "Male", "reports_to": reports_to,
    })
    emp.flags.ignore_mandatory = True
    emp.insert(ignore_permissions=True)
    return emp.name


class TestNotify(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _ensure_user(MANAGER)
        _ensure_user(REP)
        cls.manager_emp = _ensure_employee("FS Notify Test Manager", MANAGER)
        cls.rep_emp = _ensure_employee("FS Notify Test Rep", REP, reports_to=cls.manager_emp)
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()

    def tearDown(self):
        frappe.set_user("Administrator")
        self._cleanup()
        frappe.db.rollback()

    def _cleanup(self):
        frappe.db.sql(
            "delete from `tabNotification Log` where subject like %s", ("FS Notify Test%",)
        )

    def _last_notification(self, for_user):
        name = frappe.db.get_value(
            "Notification Log", {"for_user": for_user, "subject": ["like", "FS Notify Test%"]},
            "name", order_by="creation desc",
        )
        return frappe.get_doc("Notification Log", name) if name else None

    # ------------------------------------------------------------ core rule

    def test_rep_acting_on_their_own_record_notifies_the_manager(self):
        frappe.set_user(REP)
        notify.notify_employee_event(self.rep_emp, "User", REP, "FS Notify Test rep event")

        self.assertIsNotNone(self._last_notification(MANAGER))
        self.assertIsNone(self._last_notification(REP))

    def test_someone_else_acting_on_the_reps_record_notifies_the_rep(self):
        frappe.set_user("Administrator")
        notify.notify_employee_event(self.rep_emp, "User", REP, "FS Notify Test admin event")

        self.assertIsNotNone(self._last_notification(REP))
        self.assertIsNone(self._last_notification(MANAGER))

    def test_no_manager_configured_does_not_error(self):
        _ensure_user("fs.notify.orphan@example.com")
        emp = _ensure_employee("FS Notify Test Orphan Rep", "fs.notify.orphan@example.com", reports_to=None)
        frappe.set_user("fs.notify.orphan@example.com")
        # Must not raise even though there's nobody to notify.
        notify.notify_employee_event(emp, "User", "fs.notify.orphan@example.com", "FS Notify Test orphan event")

    def test_unknown_employee_does_not_error(self):
        notify.notify_employee_event(None, "User", REP, "FS Notify Test blank event")

    # ------------------------------------------------------------ sales order wiring

    def test_sales_order_hooks_skip_cleanly_without_created_by_emp(self):
        doc = frappe._dict(doctype="Sales Order", name="SAL-NOTIFY-TEST", customer="Test", customer_name="Test")
        doc.meta = frappe._dict(has_field=lambda f: False)
        doc.get = lambda f, default=None: None
        # Must not raise when the custom field isn't present on this site.
        notify.notify_sales_order_submitted(doc)
        notify.notify_sales_order_cancelled(doc)
