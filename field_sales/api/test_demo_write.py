# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the Product Demo / Demo Evaluation write path in api/demo.py.

api/test_demo.py already exercises the scorecard's type safety at the
controller level, by constructing a Demo Evaluation directly. These tests
cover the thing that cannot: whether the whitelisted create_demo/
create_evaluation/submit_evaluation endpoints - the only way a client can
reach that controller at all - can be used to sneak a mismatched rating and
measurement past it, given that the endpoint's own field handling decides
what gets copied onto a row before the controller ever sees it.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from field_sales.api.demo import (
    create_demo,
    create_evaluation,
    submit_demo,
    submit_evaluation,
    update_demo,
)

REP = "ravi.tsm@demo.local"
TERRITORY = "Kolkata Area"


def ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.new_doc(doctype)
    doc.update(values)
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


class TestDemoWrite(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = frappe.db.get_value(
            "Employee", {"user_id": REP, "status": "Active"}, "name"
        )
        cls.item = frappe.db.get_value("Item", {"is_sales_item": 1}, "name")
        cls.customer = frappe.db.get_value(
            "Customer", {"territory": TERRITORY}, "name"
        ) or frappe.db.get_value("Customer", {}, "name")

        cls.rating_param = ensure("Demo Parameter", "FS Write Test Softness", {
            "parameter_name": "FS Write Test Softness", "value_type": "Rating",
        })
        cls.minutes_param = ensure("Demo Parameter", "FS Write Test Proofing Time", {
            "parameter_name": "FS Write Test Proofing Time", "value_type": "Minutes",
            "unit": "min",
        })
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()
        frappe.set_user(REP)

    def tearDown(self):
        frappe.set_user("Administrator")
        self._cleanup()
        frappe.db.rollback()

    def _cleanup(self):
        for name in frappe.get_all("Demo Evaluation", pluck="name"):
            frappe.delete_doc("Demo Evaluation", name, force=True, ignore_permissions=True)
        for name in frappe.get_all("Product Demo", pluck="name"):
            doc = frappe.get_doc("Product Demo", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Product Demo", name, force=True, ignore_permissions=True)

    def _demo_payload(self, **overrides):
        payload = {
            "party_type": "Customer",
            "customer": self.customer,
            "demo_date": nowdate(),
            "demo_location": "On Site",
            "conducted_by": "Self",
            "territory": TERRITORY,
            "items": [{"item_code": self.item, "qty": 5, "uom": "Kg"}],
        }
        payload.update(overrides)
        return payload

    # ------------------------------------------------------------ demo create

    def test_create_returns_a_draft(self):
        result = create_demo(**self._demo_payload())
        self.assertTrue(result["name"].startswith("PD-"))
        self.assertEqual(result["docstatus"], 0)

    def test_create_forces_the_signed_in_users_own_employee(self):
        other = frappe.db.get_value(
            "Employee", {"name": ["!=", self.employee], "status": "Active"}, "name"
        )
        result = create_demo(**self._demo_payload(sales_person=other))
        doc = frappe.get_doc("Product Demo", result["name"])
        self.assertEqual(doc.sales_person, self.employee)

    def test_create_ignores_a_client_supplied_duration(self):
        result = create_demo(**self._demo_payload(
            duration=999999,
            started_on="2020-01-01 09:00:00",
            completed_on="2020-01-01 09:00:01",
        ))
        doc = frappe.get_doc("Product Demo", result["name"])
        # duration is derived from started_on/completed_on, not sent directly
        self.assertNotEqual(doc.duration, 999999)

    def test_update_edits_a_draft(self):
        name = create_demo(**self._demo_payload())["name"]
        update_demo(name, remarks="Went well")
        doc = frappe.get_doc("Product Demo", name)
        self.assertEqual(doc.remarks, "Went well")

    def test_submit_requires_at_least_one_item(self):
        name = create_demo(**self._demo_payload())["name"]
        result = submit_demo(name)
        self.assertEqual(result["docstatus"], 1)

    # ------------------------------------------------------------ evaluation

    def test_evaluation_requires_the_item_to_be_on_the_demo(self):
        demo_name = create_demo(**self._demo_payload())["name"]
        other_item = frappe.db.get_value(
            "Item", {"name": ["!=", self.item], "is_sales_item": 1}, "name"
        )
        if not other_item:
            self.skipTest("only one sellable item on this site")
        with self.assertRaises(frappe.ValidationError):
            create_evaluation(
                product_demo=demo_name, item_code=other_item,
                parameters=[{"parameter": self.rating_param, "rating": "Good"}],
            )

    def test_a_rating_against_a_measured_parameter_is_rejected_at_the_api(self):
        """The defect this doctype exists to prevent, reached through the
        endpoint a client actually calls rather than through the controller
        directly."""
        demo_name = create_demo(**self._demo_payload())["name"]
        with self.assertRaises(frappe.ValidationError):
            create_evaluation(
                product_demo=demo_name, item_code=self.item,
                parameters=[{"parameter": self.minutes_param, "rating": "Excellent"}],
            )

    def test_a_measurement_against_a_rating_parameter_is_rejected_at_the_api(self):
        demo_name = create_demo(**self._demo_payload())["name"]
        with self.assertRaises(frappe.ValidationError):
            create_evaluation(
                product_demo=demo_name, item_code=self.item,
                parameters=[{"parameter": self.rating_param, "value": 45}],
            )

    def test_a_client_sent_value_type_cannot_relabel_a_row(self):
        """Even if the client names a value_type that matches its bogus
        value, the endpoint never copies that field onto the row - the
        controller always looks value_type up from the Demo Parameter
        itself."""
        demo_name = create_demo(**self._demo_payload())["name"]
        with self.assertRaises(frappe.ValidationError):
            create_evaluation(
                product_demo=demo_name, item_code=self.item,
                parameters=[{
                    "parameter": self.minutes_param,
                    "value_type": "Rating",
                    "rating": "Excellent",
                }],
            )

    def test_a_valid_scorecard_is_accepted(self):
        demo_name = create_demo(**self._demo_payload())["name"]
        result = create_evaluation(
            product_demo=demo_name, item_code=self.item, outcome="Successful",
            order_received=1,
            parameters=[
                {"parameter": self.rating_param, "rating": "Good"},
                {"parameter": self.minutes_param, "value": 12},
            ],
        )
        doc = frappe.get_doc("Demo Evaluation", result["name"])
        self.assertEqual(len(doc.parameters), 2)

    def test_submit_evaluation_requires_an_outcome(self):
        demo_name = create_demo(**self._demo_payload())["name"]
        result = create_evaluation(
            product_demo=demo_name, item_code=self.item,
            parameters=[{"parameter": self.rating_param, "rating": "Good"}],
        )
        with self.assertRaises(frappe.ValidationError):
            submit_evaluation(result["name"])

    def test_submit_evaluation_succeeds_once_outcome_is_set(self):
        demo_name = create_demo(**self._demo_payload())["name"]
        result = create_evaluation(
            product_demo=demo_name, item_code=self.item, outcome="Successful",
            order_received=1,
            parameters=[{"parameter": self.rating_param, "rating": "Good"}],
        )
        submitted = submit_evaluation(result["name"])
        self.assertEqual(submitted["outcome"], "Successful")
