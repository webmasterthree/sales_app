# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the Field Trial Plan write path."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from field_sales.api.trial_plan import (
    create_trial_plan,
    submit_trial_plan,
    update_attendance,
    update_trial_plan,
)

REP = "ravi.tsm@demo.local"
REP_TERRITORY = "Kolkata Area"


def ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.new_doc(doctype)
    doc.update(values)
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


class TestFieldTrialPlanWrite(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = frappe.db.get_value("Customer", {}, "name")
        cls.channel_partner = frappe.db.get_value(
            "Customer", {"name": ["!=", cls.customer]}, "name"
        )
        cls.item = frappe.db.get_value("Item", {"has_variants": 0}, "name")
        # The follow-up-order tests book a real Sales Order, and
        # enforce_sales_order_rates (field_sales.pricing) refuses to price a
        # line with no Item Price on the resolved selling list at all.
        if not frappe.db.exists(
            "Item Price", {"item_code": cls.item, "price_list": "Standard Selling", "selling": 1}
        ):
            price = frappe.new_doc("Item Price")
            price.update({
                "item_code": cls.item, "price_list": "Standard Selling",
                "selling": 1, "price_list_rate": 100,
            })
            price.flags.ignore_mandatory = True
            price.insert(ignore_permissions=True)
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()
        # Everything under test runs as an actual field rep - the endpoints
        # deliberately refuse to file a trial against a user with no linked
        # Employee, the same guard every other write endpoint in this app has.
        frappe.set_user(REP)

    def tearDown(self):
        frappe.set_user("Administrator")
        self._cleanup()
        frappe.db.rollback()

    def _cleanup(self):
        for name in frappe.get_all("Field Trial Plan", pluck="name"):
            doc = frappe.get_doc("Field Trial Plan", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Field Trial Plan", name, force=True, ignore_permissions=True)

    def _book_order(self, customer):
        """A real Sales Order to link as a trial's follow-up. Booked as
        Administrator - ERPNext's Sales Order controller separately checks
        read/select on the customer's receivable Account regardless of
        ignore_permissions (see catalog.py's _as_a_privileged_user for the
        same quirk on the app's own order-creation endpoint), which the REP
        user this test otherwise runs as does not hold."""
        current = frappe.session.user
        frappe.set_user("Administrator")
        try:
            order = frappe.get_doc({
                "doctype": "Sales Order",
                "customer": customer,
                "delivery_date": add_days(nowdate(), 7),
                "items": [{"item_code": self.item, "qty": 1, "rate": 1}],
            })
            order.flags.ignore_mandatory = True
            order.insert(ignore_permissions=True)
            return order.name
        finally:
            frappe.set_user(current)

    def _payload(self, **overrides):
        payload = {
            "visit_type": "Primary",
            "customer": self.customer,
            "item_code": self.item,
            "delivery_date": nowdate(),
            "territory": REP_TERRITORY,
        }
        payload.update(overrides)
        return payload

    # ------------------------------------------------------------ create

    def test_create_defaults_the_rep_and_status(self):
        result = create_trial_plan(**self._payload())
        doc = frappe.get_doc("Field Trial Plan", result["name"])
        self.assertEqual(doc.docstatus, 0)
        self.assertEqual(doc.status, "Scheduled")
        self.assertEqual(
            doc.sales_person,
            frappe.db.get_value("Employee", {"user_id": REP}, "name"),
        )

    def test_trial_ignores_client_visit_type_and_derives_from_the_customer(self):
        """visit_type/channel_partner are not something a rep sends for a
        trial - they're copied from the customer's own master record
        (customer_level/custom_channel_partner), the same as Field Visit's
        identical derivation. A client claiming Secondary for a Primary
        customer is simply overridden, not rejected."""
        result = create_trial_plan(**self._payload(visit_type="Secondary", channel_partner=self.channel_partner))
        doc = frappe.get_doc("Field Trial Plan", result["name"])
        self.assertEqual(doc.visit_type, "Primary")
        self.assertFalse(doc.channel_partner)

    def test_a_secondary_customers_channel_partner_is_copied_onto_the_trial(self):
        frappe.db.set_value(
            "Customer", self.customer,
            {"customer_level": "Secondary", "custom_channel_partner": self.channel_partner},
        )
        try:
            result = create_trial_plan(**self._payload())
            doc = frappe.get_doc("Field Trial Plan", result["name"])
            self.assertEqual(doc.visit_type, "Secondary")
            self.assertEqual(doc.channel_partner, self.channel_partner)
        finally:
            frappe.db.set_value(
                "Customer", self.customer,
                {"customer_level": "Primary", "custom_channel_partner": None},
            )

    def test_client_cannot_set_its_own_status(self):
        """`status` is not in WRITABLE_FIELDS at all - the controller decides
        it from docstatus and the attendance checklist, not from whatever a
        client sends."""
        result = create_trial_plan(**self._payload(status="Completed"))
        doc = frappe.get_doc("Field Trial Plan", result["name"])
        self.assertEqual(doc.status, "Scheduled")

    # ------------------------------------------------------------ update / submit

    def test_only_a_draft_can_be_updated(self):
        result = create_trial_plan(**self._payload())
        submit_trial_plan(result["name"])
        with self.assertRaises(frappe.ValidationError):
            update_trial_plan(result["name"], delivery_date=add_days(nowdate(), 1))

    def test_submit_moves_docstatus_but_not_status(self):
        result = create_trial_plan(**self._payload())
        submitted = submit_trial_plan(result["name"])
        self.assertEqual(submitted["docstatus"], 1)
        self.assertEqual(submitted["status"], "Scheduled")

    # ------------------------------------------------------------ attendance

    def test_attendance_cannot_be_recorded_before_submit(self):
        result = create_trial_plan(**self._payload())
        with self.assertRaises(frappe.ValidationError):
            update_attendance(result["name"], sample_distributed=1)

    def test_status_completes_only_once_every_attendance_item_is_done(self):
        result = create_trial_plan(**self._payload())
        submit_trial_plan(result["name"])

        after_one = update_attendance(result["name"], sample_distributed=1)
        self.assertEqual(after_one["status"], "Scheduled")

        after_two = update_attendance(result["name"], feedback_collected=1)
        self.assertEqual(after_two["status"], "Scheduled")

        order_name = self._book_order(self.customer)

        completed = update_attendance(result["name"], follow_up_order=order_name)
        self.assertEqual(completed["status"], "Completed")

    def test_follow_up_order_must_belong_to_the_trials_customer(self):
        result = create_trial_plan(**self._payload())
        submit_trial_plan(result["name"])

        other_order_name = self._book_order(self.channel_partner)

        with self.assertRaises(frappe.ValidationError):
            update_attendance(result["name"], follow_up_order=other_order_name)
