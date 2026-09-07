# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the field sales authentication endpoints.

Most of these exist to pin down defects found in the app this was derived
from: an OTP returned in its own response body, a globally shared OTP cache
key, and an attempt counter that never actually counted.
"""

import re

import frappe
from frappe.tests.utils import FrappeTestCase

from field_sales.api import auth

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


class TestFieldSalesAuth(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.alice = make_user("fs.alice@example.com", "Alice")
        cls.bob = make_user("fs.bob@example.com", "Bob")
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        for user in (self.alice, self.bob):
            auth.clear_otp(user)

        # Capture outgoing mail rather than delivering it: the test site has no
        # outgoing email account, and the message body is where the code lives.
        self.outbox = []
        self._real_sendmail = frappe.sendmail
        frappe.sendmail = lambda **kwargs: self.outbox.append(kwargs)

    def tearDown(self):
        frappe.sendmail = self._real_sendmail
        for user in (self.alice, self.bob):
            auth.clear_otp(user)
        frappe.set_user("Administrator")

    # ------------------------------------------------------------ secrecy

    def test_request_otp_does_not_return_the_code(self):
        """The implementation this replaces put the code straight in the response."""
        result = auth.request_login_otp(self.alice)
        blob = frappe.as_json(result)

        self.assertNotIn("otp", blob.lower())
        for token in re.findall(r"\d+", blob):
            self.assertNotEqual(
                len(token),
                auth.OTP_LENGTH,
                f"response leaked something shaped like a code: {token}",
            )

        # the code really was generated and mailed, just not handed back
        self.assertTrue(self.outbox, "no email was sent")
        self.assertIsNotNone(auth._read_otp(self.alice))

    def test_stored_code_is_hashed(self):
        otp = self._issue(self.alice)
        stored = auth._read_otp(self.alice)
        self.assertNotEqual(stored, otp)
        self.assertEqual(len(stored), 64)
        self.assertNotIn(otp, stored)

    # ------------------------------------------------------------ isolation

    def test_codes_are_scoped_per_user(self):
        """Two concurrent requests must not share one cache slot."""
        self._issue(self.alice)
        bob_otp = self._issue(self.bob)
        self.assertNotEqual(auth._key("otp", self.alice), auth._key("otp", self.bob))

        # Bob's code must not open Alice's account
        with self.assertRaises(frappe.AuthenticationError):
            auth.consume_otp(self.alice, bob_otp)

        # and Bob's own code still works
        self.assertEqual(auth.consume_otp(self.bob, bob_otp), self.bob)

    # ------------------------------------------------------------ verification

    def test_correct_code_resolves_to_the_user(self):
        otp = self._issue(self.alice)
        self.assertEqual(auth.consume_otp(self.alice, otp), self.alice)

    def test_code_is_single_use(self):
        otp = self._issue(self.alice)
        auth.consume_otp(self.alice, otp)
        with self.assertRaises(frappe.AuthenticationError):
            auth.consume_otp(self.alice, otp)

    def test_wrong_code_is_rejected(self):
        otp = self._issue(self.alice)
        with self.assertRaises(frappe.AuthenticationError):
            auth.consume_otp(self.alice, self._other_than(otp))

    def test_attempts_are_counted(self):
        """The counter has to survive across calls - it previously did not."""
        otp = self._issue(self.alice)
        wrong = self._other_than(otp)

        for expected in range(1, auth.OTP_MAX_ATTEMPTS):
            with self.assertRaises(frappe.AuthenticationError):
                auth.consume_otp(self.alice, wrong)
            self.assertEqual(
                int(auth._redis().get(auth._key("attempts", self.alice)) or 0),
                expected,
                "attempt counter did not advance",
            )

    def test_code_is_burned_at_the_attempt_limit(self):
        otp = self._issue(self.alice)
        wrong = self._other_than(otp)

        for _i in range(auth.OTP_MAX_ATTEMPTS):
            with self.assertRaises(frappe.AuthenticationError):
                auth.consume_otp(self.alice, wrong)

        self.assertIsNone(auth._read_otp(self.alice), "code survived the attempt limit")
        # even the correct code is now useless
        with self.assertRaises(frappe.AuthenticationError):
            auth.consume_otp(self.alice, otp)

    def test_expired_or_absent_code_is_rejected(self):
        with self.assertRaises(frappe.AuthenticationError):
            auth.consume_otp(self.alice, "123456")

    # ------------------------------------------------------------ enumeration

    def test_unknown_address_gets_an_identical_response(self):
        known = auth.request_login_otp(self.alice)
        unknown = auth.request_login_otp("nobody.here@example.com")
        self.assertEqual(known, unknown)

    def test_unknown_address_cannot_verify(self):
        with self.assertRaises(frappe.AuthenticationError):
            auth.consume_otp("nobody.here@example.com", "123456")

    def test_delivery_failure_does_not_become_an_oracle(self):
        """A send error must not distinguish a real address from a fake one.

        Frappe returns anything in the message log as `_server_messages`, so an
        SMTP failure that only fires for real accounts is an enumeration
        channel even when the JSON body is identical.
        """

        def explode(**kwargs):
            frappe.msgprint("Please setup default outgoing Email Account")
            raise Exception("smtp is down")

        frappe.sendmail = explode

        frappe.local.message_log = []
        known = auth.request_login_otp(self.alice)
        known_messages = list(frappe.local.message_log or [])

        frappe.local.message_log = []
        unknown = auth.request_login_otp("nobody.here@example.com")
        unknown_messages = list(frappe.local.message_log or [])

        self.assertEqual(known, unknown)
        self.assertEqual(
            known_messages,
            unknown_messages,
            "the message log distinguishes a real address from a fake one",
        )

    def test_disabled_user_cannot_receive_or_verify(self):
        frappe.db.set_value("User", self.bob, "enabled", 0)
        try:
            auth.request_login_otp(self.bob)
            self.assertFalse(self.outbox, "a disabled account was emailed a code")
            with self.assertRaises(frappe.AuthenticationError):
                auth.consume_otp(self.bob, "123456")
        finally:
            frappe.db.set_value("User", self.bob, "enabled", 1)

    # ------------------------------------------------------------ session

    def test_session_requires_authentication(self):
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.AuthenticationError):
                auth.session()
        finally:
            frappe.set_user("Administrator")

    def test_session_payload_shape(self):
        payload = auth.session_payload(self.alice)
        for field in ("user", "full_name", "roles", "territories"):
            self.assertIn(field, payload)
        self.assertEqual(payload["user"], self.alice)
        self.assertIsInstance(payload["roles"], list)

    # ------------------------------------------------------------ update_profile

    def test_update_profile_requires_authentication(self):
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.AuthenticationError):
                auth.update_profile(mobile_no="9999999999")
        finally:
            frappe.set_user("Administrator")

    def test_update_profile_writes_allowlisted_fields(self):
        frappe.set_user(self.alice)
        try:
            result = auth.update_profile(
                first_name="Alicia",
                mobile_no="9876543210",
                phone="9123456789",
                mute_sounds=1,
            )
        finally:
            frappe.set_user("Administrator")

        self.assertEqual(result["first_name"], "Alicia")
        self.assertEqual(result["mobile_no"], "9876543210")
        self.assertEqual(result["phone"], "9123456789")
        self.assertEqual(frappe.db.get_value("User", self.alice, "first_name"), "Alicia")

    def test_update_profile_only_ever_touches_the_caller(self):
        """The endpoint must never be able to edit someone else's record."""
        frappe.db.set_value("User", self.bob, "mobile_no", "0000000000")

        frappe.set_user(self.alice)
        try:
            auth.update_profile(name=self.bob, user=self.bob, mobile_no="1111111111")
        finally:
            frappe.set_user("Administrator")

        self.assertEqual(frappe.db.get_value("User", self.alice, "mobile_no"), "1111111111")
        self.assertEqual(frappe.db.get_value("User", self.bob, "mobile_no"), "0000000000")

    def test_update_profile_ignores_permission_relevant_fields(self):
        """Roles, email and username are never on the allow-list."""
        self.assertNotIn("roles", auth.WRITABLE_PROFILE_FIELDS)
        self.assertNotIn("email", auth.WRITABLE_PROFILE_FIELDS)
        self.assertNotIn("username", auth.WRITABLE_PROFILE_FIELDS)
        self.assertNotIn("user_type", auth.WRITABLE_PROFILE_FIELDS)

        frappe.set_user(self.alice)
        try:
            auth.update_profile(email="hijacked@example.com", user_type="System User")
        finally:
            frappe.set_user("Administrator")

        self.assertEqual(frappe.db.get_value("User", self.alice, "email"), self.alice)

    # ------------------------------------------------------------ helpers

    def _issue(self, user: str) -> str:
        """Request a code and recover the plaintext from the outgoing email."""
        before = len(self.outbox)
        auth.request_login_otp(user)
        self.assertGreater(len(self.outbox), before, "no email was sent")
        body = self.outbox[-1].get("message", "")
        match = re.search(r"<b>(\d{%d})</b>" % auth.OTP_LENGTH, body)
        self.assertIsNotNone(match, "no code found in the outgoing email")
        return match.group(1)

    @staticmethod
    def _other_than(otp: str) -> str:
        return "000000" if otp != "000000" else "111111"
