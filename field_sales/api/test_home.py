# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the home screen: module grid, scoreboard, attendance, notifications."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from field_sales.api import home

REP = "ravi.tsm@demo.local"


class TestHome(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = frappe.db.get_value("Employee", {"user_id": REP}, "name")
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()

    def tearDown(self):
        frappe.set_user("Administrator")
        self._cleanup()
        frappe.db.rollback()

    def _cleanup(self):
        # Notification Log carries a permission query condition restricting rows
        # to the signed-in user, so get_all as Administrator cannot see another
        # user's notifications. Delete directly.
        frappe.db.sql(
            "delete from `tabNotification Log` where subject like %s", ("FS Test%",)
        )

    def _notification(self, subject="FS Test something happened", read=0, user=REP,
                      about=None):
        doc = frappe.new_doc("Notification Log")
        doc.update({
            "subject": subject, "for_user": user, "from_user": "Administrator",
            "type": "Alert", "read": read, "email_content": "<p>body</p>",
            # Notification Log dereferences document_type on insert, and
            # `mohan_impex` hooks after_insert with a dedup that deletes any
            # log sharing (for_user, document_type, document_name, type) within
            # 90 seconds - so each fixture points at a distinct document.
            "document_type": "User",
            "document_name": about or user,
        })
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return doc

    # ------------------------------------------------------------ module grid

    def test_grid_returns_tiles(self):
        grid = home.module_grid("Administrator")
        self.assertTrue(grid)
        names = [t["name"] for t in grid]
        self.assertIn("field_visit", names)

    def test_grid_nests_requisitions(self):
        grid = home.module_grid("Administrator")
        group = next((t for t in grid if t["name"] == "requisitions"), None)
        self.assertIsNotNone(group, "the requisitions group is missing")
        child_names = [c["name"] for c in group["children"]]
        self.assertIn("sample_request", child_names)
        self.assertIn("product_demo", child_names)

    def test_grid_carries_routes_not_server_urls(self):
        """The original returned a half-formed desk URL the client could not use."""
        grid = home.module_grid("Administrator")
        visit = next(t for t in grid if t["name"] == "field_visit")
        self.assertEqual(visit["route"], "/visits")
        self.assertNotIn("http", visit["route"])

    def test_grid_carries_icon_names_not_signed_urls(self):
        """The original signed a JWT per icon per home screen load."""
        grid = home.module_grid("Administrator")
        visit = next(t for t in grid if t["name"] == "field_visit")
        self.assertEqual(visit["icon"], "visit")
        self.assertNotIn("token", visit["icon"] or "")

    def test_grid_hides_tiles_the_user_cannot_read(self):
        grid = home.module_grid("Guest")
        names = [t["name"] for t in grid]
        self.assertNotIn("field_visit", names)

    def test_a_group_with_no_visible_children_is_dropped(self):
        grid = home.module_grid("Guest")
        self.assertNotIn("requisitions", [t["name"] for t in grid])

    def test_grid_respects_enabled(self):
        frappe.db.set_value("Field Sales Module", "complaints", "enabled", 0)
        try:
            grid = home.module_grid("Administrator")
            self.assertNotIn("complaints", [t["name"] for t in grid])
        finally:
            frappe.db.set_value("Field Sales Module", "complaints", "enabled", 1)

    # ------------------------------------------------------------ scoreboard

    def test_scoreboard_has_the_two_counters(self):
        board = home.scoreboard(REP)
        self.assertEqual([b["name"] for b in board], ["visits", "orders"])
        for entry in board:
            self.assertIsInstance(entry["count"], int)

    def test_scoreboard_counts_are_not_negative(self):
        for entry in home.scoreboard(REP):
            self.assertGreaterEqual(entry["count"], 0)

    def test_scoreboard_survives_a_missing_doctype(self):
        """A broken panel must not take the home screen down."""
        original = home.SCORES[:]
        home.SCORES.append(("ghost", "Ghost", "No Such Doctype", None, "creation"))
        try:
            board = home.scoreboard(REP)
            ghost = next(b for b in board if b["name"] == "ghost")
            self.assertEqual(ghost["count"], 0)
        finally:
            home.SCORES[:] = original

    # ------------------------------------------------------------ attendance

    def test_check_in_state_shape(self):
        state = home.check_in_state(REP)
        self.assertIn("checked_in", state)
        self.assertEqual(state["employee"], self.employee)

    def test_punch_in_then_out(self):
        frappe.set_user(REP)
        try:
            after_in = home.punch("IN", latitude=22.5726, longitude=88.3639)
            self.assertTrue(after_in["checked_in"])
            after_out = home.punch("OUT")
            self.assertFalse(after_out["checked_in"])
        finally:
            frappe.set_user("Administrator")

    def test_punch_rejects_a_bad_log_type(self):
        frappe.set_user(REP)
        try:
            with self.assertRaises(frappe.ValidationError):
                home.punch("SIDEWAYS")
        finally:
            frappe.set_user("Administrator")

    # ------------------------------------------------------------ notifications

    def test_notifications_are_listed_newest_first(self):
        self._notification("FS Test older", about="Administrator")
        self._notification("FS Test newer", about="Guest")
        frappe.set_user(REP)
        try:
            result = home.notifications()
        finally:
            frappe.set_user("Administrator")
        subjects = [r["subject"] for r in result["records"] if r["subject"].startswith("FS Test")]
        self.assertEqual(subjects[:2], ["FS Test newer", "FS Test older"])

    def test_unread_filter(self):
        self._notification("FS Test unread", read=0, about="Administrator")
        self._notification("FS Test read", read=1, about="Guest")
        frappe.set_user(REP)
        try:
            unread = home.notifications(unread_only=1)
        finally:
            frappe.set_user("Administrator")
        subjects = [r["subject"] for r in unread["records"]]
        self.assertIn("FS Test unread", subjects)
        self.assertNotIn("FS Test read", subjects)

    def test_marking_one_read(self):
        note = self._notification("FS Test mark me", read=0)
        frappe.set_user(REP)
        try:
            home.mark_notification_read(name=note.name)
        finally:
            frappe.set_user("Administrator")
        self.assertEqual(frappe.db.get_value("Notification Log", note.name, "read"), 1)

    def test_marking_all_read(self):
        self._notification("FS Test a", read=0, about="Administrator")
        self._notification("FS Test b", read=0, about="Guest")
        frappe.set_user(REP)
        try:
            result = home.mark_notification_read(all_of_them=1)
        finally:
            frappe.set_user("Administrator")
        self.assertEqual(result["unread_count"], 0)

    def test_cannot_mark_somebody_elses_notification(self):
        note = self._notification("FS Test not yours", user="priya.tsm@demo.local")
        frappe.set_user(REP)
        try:
            with self.assertRaises(frappe.PermissionError):
                home.mark_notification_read(name=note.name)
        finally:
            frappe.set_user("Administrator")
        self.assertEqual(frappe.db.get_value("Notification Log", note.name, "read"), 0)

    # ------------------------------------------------------------ whole screen

    def test_home_returns_every_panel(self):
        frappe.set_user(REP)
        try:
            payload = home.home()
        finally:
            frappe.set_user("Administrator")
        for key in ("user", "modules", "scoreboard", "attendance", "unread_notifications"):
            self.assertIn(key, payload)
        self.assertEqual(payload["user"]["employee"], self.employee)
        self.assertIn("Kolkata Area", payload["user"]["territories"])
