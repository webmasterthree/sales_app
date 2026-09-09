# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for Field Sales Branding and the endpoints that read it
(api/branding.py) - the app name/icon is meant to update without a
rebuild, so these pin that changing the Single actually changes what
those endpoints return."""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from field_sales.api import branding


class TestFieldSalesBranding(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self._reset()

    def tearDown(self):
        self._reset()
        frappe.set_user("Administrator")

    def _reset(self):
        doc = frappe.get_single("Field Sales Branding")
        doc.app_name = "Field Sales"
        doc.app_description = None
        doc.app_icon = None
        doc.save(ignore_permissions=True)

    def test_blank_falls_back_to_the_default_name(self):
        doc = frappe.get_single("Field Sales Branding")
        doc.app_name = ""
        doc.flags.ignore_mandatory = True
        doc.save(ignore_permissions=True)
        self.assertEqual(branding.get_app_name(), branding.DEFAULT_APP_NAME)

    def test_a_configured_name_is_used(self):
        doc = frappe.get_single("Field Sales Branding")
        doc.app_name = "Mohan Impex Sales"
        doc.save(ignore_permissions=True)
        self.assertEqual(branding.get_app_name(), "Mohan Impex Sales")

    def test_blank_description_falls_back_to_the_default(self):
        self.assertEqual(branding.get_app_description(), branding.DEFAULT_APP_DESCRIPTION)

    def test_a_configured_description_is_used(self):
        doc = frappe.get_single("Field Sales Branding")
        doc.app_description = "Custom field sales workflow for Mohan Impex."
        doc.save(ignore_permissions=True)
        self.assertEqual(branding.get_app_description(), "Custom field sales workflow for Mohan Impex.")

    def test_manifest_reflects_the_configured_description(self):
        doc = frappe.get_single("Field Sales Branding")
        doc.app_description = "Custom field sales workflow for Mohan Impex."
        doc.save(ignore_permissions=True)
        body = json.loads(branding.manifest().data)
        self.assertEqual(body["description"], "Custom field sales workflow for Mohan Impex.")

    def test_no_icon_falls_back_to_the_default_path(self):
        self.assertEqual(branding.get_icon_path(), branding.DEFAULT_ICON_PATH)

    def test_a_private_icon_is_refused(self):
        doc = frappe.get_single("Field Sales Branding")
        doc.app_icon = "/private/files/some-icon.png"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_a_public_icon_is_accepted_and_used(self):
        doc = frappe.get_single("Field Sales Branding")
        doc.app_icon = "/files/some-icon.png"
        doc.save(ignore_permissions=True)
        self.assertEqual(branding.get_icon_path(), "/files/some-icon.png")

    def test_manifest_reflects_the_configured_name_and_icon(self):
        doc = frappe.get_single("Field Sales Branding")
        doc.app_name = "Mohan Impex Sales"
        doc.app_icon = "/files/some-icon.png"
        doc.save(ignore_permissions=True)

        response = branding.manifest()
        body = json.loads(response.data)
        self.assertEqual(body["name"], "Mohan Impex Sales")
        self.assertEqual(body["short_name"], "Mohan Impex Sales")
        self.assertTrue(all(icon["src"].endswith("/files/some-icon.png") for icon in body["icons"]))
        self.assertTrue(all(icon["type"] == "image/png" for icon in body["icons"]))
        self.assertEqual(response.mimetype, "application/manifest+json")

    def test_manifest_declares_the_icons_real_type_not_always_png(self):
        # A real bug: every icon entry declared "image/png" regardless of
        # the actual uploaded file - a browser that checks the declared
        # type against the real bytes can silently refuse a mismatched
        # icon (e.g. a genuine .jpg advertised as png).
        doc = frappe.get_single("Field Sales Branding")
        doc.app_icon = "/files/some-icon.jpg"
        doc.save(ignore_permissions=True)

        body = json.loads(branding.manifest().data)
        self.assertTrue(all(icon["type"] == "image/jpeg" for icon in body["icons"]))

    def test_icon_redirects_to_the_configured_file(self):
        doc = frappe.get_single("Field Sales Branding")
        doc.app_icon = "/files/some-icon.png"
        doc.save(ignore_permissions=True)

        branding.icon()
        self.assertEqual(frappe.local.response["type"], "redirect")
        self.assertTrue(frappe.local.response["location"].endswith("/files/some-icon.png"))
