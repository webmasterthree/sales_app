# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for relaying a new Notification Log entry as an FCM push."""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from field_sales.api import push

REP = "ravi.tsm@demo.local"


class TestPush(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()

    def tearDown(self):
        frappe.set_user("Administrator")
        self._cleanup()
        frappe.db.rollback()

    def _cleanup(self):
        frappe.db.sql(
            "delete from `tabNotification Log` where subject like %s", ("FS Push Test%",)
        )

    def _notification(self, document_type="User", document_name=None):
        doc = frappe.new_doc("Notification Log")
        doc.update({
            "subject": "FS Push Test something happened",
            "for_user": REP,
            "from_user": "Administrator",
            "type": "Alert",
            "email_content": "<p>body</p>",
            "document_type": document_type,
            "document_name": document_name or REP,
        })
        doc.flags.ignore_mandatory = True
        doc.flags.ignore_links = True  # document_name may not be a real record in these fixtures
        return doc

    def _mock_relay(self, enabled=True):
        relay = MagicMock()
        relay.is_enabled.return_value = enabled
        relay.send_notification_to_user.return_value = True
        return patch("frappe.push_notification.PushNotification", return_value=relay), relay

    def test_relays_to_the_recipients_registered_devices(self):
        patcher, relay = self._mock_relay()
        with patcher:
            self._notification(document_type="Field Visit", document_name="FV-TEST-0001").insert(
                ignore_permissions=True
            )

        relay.send_notification_to_user.assert_called_once()
        args, kwargs = relay.send_notification_to_user.call_args
        self.assertEqual(args[0], REP)
        self.assertEqual(args[1], "FS Push Test something happened")
        self.assertIn("/field_sales_app/visits/FV-TEST-0001", kwargs["link"])

    def test_unmapped_document_type_still_pushes_but_links_home(self):
        patcher, relay = self._mock_relay()
        with patcher:
            self._notification(document_type="ToDo", document_name="TODO-0001").insert(
                ignore_permissions=True
            )

        relay.send_notification_to_user.assert_called_once()
        _, kwargs = relay.send_notification_to_user.call_args
        self.assertTrue(kwargs["link"].endswith("/field_sales_app"))

    def test_skips_relay_entirely_when_disabled(self):
        patcher, relay = self._mock_relay(enabled=False)
        with patcher:
            self._notification().insert(ignore_permissions=True)

        relay.send_notification_to_user.assert_not_called()

    def test_a_relay_error_never_blocks_the_notification_log_insert(self):
        relay = MagicMock()
        relay.is_enabled.return_value = True
        relay.send_notification_to_user.side_effect = Exception("relay unreachable")
        with patch("frappe.push_notification.PushNotification", return_value=relay):
            doc = self._notification()
            doc.insert(ignore_permissions=True)  # must not raise

        self.assertTrue(frappe.db.exists("Notification Log", doc.name))
