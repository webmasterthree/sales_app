# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the Profile screen's support and legal content endpoints."""

import frappe
from frappe.tests.utils import FrappeTestCase

from field_sales.api import support

PASSWORD = "Str0ng-Test-Passw0rd!"


def make_user(email: str, first_name: str) -> str:
    if frappe.db.exists("User", email):
        return email
    user = frappe.new_doc("User")
    user.update(
        {
            "email": email,
            "first_name": first_name,
            "send_welcome_email": 0,
            "enabled": 1,
            "user_type": "System User",
            "new_password": PASSWORD,
        }
    )
    user.insert(ignore_permissions=True)
    return user.name


class TestFieldSalesSupport(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rep = make_user("fs.support.rep@example.com", "Rep")
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self.settings = frappe.get_single("Field Sales Settings")
        self._before = {
            "support_phone": self.settings.support_phone,
            "support_email": self.settings.support_email,
            "support_hours": self.settings.support_hours,
            "privacy_policy": self.settings.privacy_policy,
            "terms_of_use": self.settings.terms_of_use,
        }

    def tearDown(self):
        frappe.set_user("Administrator")
        settings = frappe.get_single("Field Sales Settings")
        settings.update(self._before)
        settings.flags.ignore_mandatory = True
        settings.save(ignore_permissions=True)
        frappe.set_user("Administrator")

    def test_support_info_requires_authentication(self):
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.AuthenticationError):
                support.support_info()
        finally:
            frappe.set_user("Administrator")

    def test_legal_info_requires_authentication(self):
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.AuthenticationError):
                support.legal_info()
        finally:
            frappe.set_user("Administrator")

    def test_any_signed_in_user_can_read_support_info(self):
        settings = frappe.get_single("Field Sales Settings")
        settings.support_phone = "+91-1800-000-000"
        settings.support_email = "help@example.com"
        settings.support_hours = "Mon-Fri, 9-6"
        settings.flags.ignore_mandatory = True
        settings.save(ignore_permissions=True)

        frappe.set_user(self.rep)
        try:
            result = support.support_info()
        finally:
            frappe.set_user("Administrator")

        self.assertEqual(result["phone"], "+91-1800-000-000")
        self.assertEqual(result["email"], "help@example.com")
        self.assertEqual(result["hours"], "Mon-Fri, 9-6")

    def test_any_signed_in_user_can_read_legal_info(self):
        settings = frappe.get_single("Field Sales Settings")
        settings.privacy_policy = "We respect your privacy."
        settings.terms_of_use = "Use this responsibly."
        settings.flags.ignore_mandatory = True
        settings.save(ignore_permissions=True)

        frappe.set_user(self.rep)
        try:
            result = support.legal_info()
        finally:
            frappe.set_user("Administrator")

        self.assertEqual(result["privacy_policy"], "We respect your privacy.")
        self.assertEqual(result["terms_of_use"], "Use this responsibly.")
