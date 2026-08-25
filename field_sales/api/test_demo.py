# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for Product Demo and the evaluation scorecard."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from field_sales.api.demo import DEMO_CONFIG, EVALUATION_CONFIG
from field_sales.api.listing import paginated_list
from field_sales.field_sales.doctype.demo_evaluation.demo_evaluation import summarise

TERRITORY = "Kolkata Area"
OTHER_TERRITORY = "Pune Area"


def ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.new_doc(doctype)
    doc.update(values)
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


class TestProductDemo(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rating_param = ensure("Demo Parameter", "FS Test Crumb Softness", {
            "parameter_name": "FS Test Crumb Softness", "value_type": "Rating",
        })
        cls.minutes_param = ensure("Demo Parameter", "FS Test Proofing Time", {
            "parameter_name": "FS Test Proofing Time", "value_type": "Minutes",
            "unit": "min",
        })
        cls.remarks_param = ensure("Demo Parameter", "FS Test Dough Handling", {
            "parameter_name": "FS Test Dough Handling", "value_type": "Rating",
            "requires_remarks": 1,
        })
        cls.customer = frappe.db.get_value("Customer", {}, "name")
        cls.employee = frappe.db.get_value(
            "Employee", {"user_id": "ravi.tsm@demo.local"}, "name")
        cls.other_employee = frappe.db.get_value(
            "Employee", {"user_id": "priya.tsm@demo.local"}, "name")
        cls.item = frappe.db.get_value("Item", {"is_sales_item": 1}, "name")
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()

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

    def _demo(self, territory=TERRITORY, employee=None, status=None, **overrides):
        doc = frappe.new_doc("Product Demo")
        doc.update({
            "party_type": "Customer",
            "customer": self.customer,
            "demo_date": nowdate(),
            "demo_location": "On Site",
            "conducted_by": "Self",
            "sales_person": employee or self.employee,
            "territory": territory,
        })
        doc.update(overrides)
        doc.append("items", {
            "item_code": self.item, "qty": 5, "uom": "Kg",
            "competitor_item": "Rival improver", "monthly_consumption": 120,
        })
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        if status:
            frappe.db.set_value("Product Demo", doc.name, "status", status)
            doc.reload()
        return doc

    def _evaluation(self, demo, lines=None, **overrides):
        doc = frappe.new_doc("Demo Evaluation")
        doc.update({
            "product_demo": demo.name,
            "item_code": self.item,
            "evaluated_on": nowdate(),
            "outcome": "Successful",
            "order_received": 1,
        })
        doc.update(overrides)
        for line in (lines if lines is not None else
                     [{"parameter": self.rating_param, "rating": "Good"}]):
            doc.append("parameters", line)
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return doc

    # ------------------------------------------------------------ demo

    def test_a_demo_saves(self):
        doc = self._demo()
        self.assertTrue(doc.name.startswith("PD-"))
        self.assertEqual(doc.status, "Pending")
        self.assertEqual(len(doc.items), 1)

    def test_demo_requires_items(self):
        doc = frappe.new_doc("Product Demo")
        doc.update({"demo_date": nowdate(), "sales_person": self.employee,
                    "territory": TERRITORY})
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)

    def test_demo_records_the_incumbent(self):
        """Knowing who you are displacing is the point of a trial."""
        doc = self._demo()
        self.assertEqual(doc.items[0].competitor_item, "Rival improver")
        self.assertEqual(doc.items[0].monthly_consumption, 120)

    def test_demo_list_and_tabs(self):
        pending = self._demo()
        completed = self._demo(status="Completed")
        all_rows = paginated_list(DEMO_CONFIG, form={}, user="Administrator")
        self.assertEqual(all_rows["total_count"], 2)
        done = paginated_list(DEMO_CONFIG, form={"tab": "completed"}, user="Administrator")
        self.assertEqual([r["name"] for r in done["records"]], [completed.name])

    def test_demo_list_is_territory_scoped(self):
        mine = self._demo(territory=TERRITORY)
        theirs = self._demo(territory=OTHER_TERRITORY, employee=self.other_employee)
        result = paginated_list(DEMO_CONFIG, form={}, user="ravi.tsm@demo.local")
        names = [r["name"] for r in result["records"]]
        self.assertIn(mine.name, names)
        self.assertNotIn(theirs.name, names)

    def test_demo_list_injection(self):
        self._demo()
        result = paginated_list(
            DEMO_CONFIG, form={"search_text": '" or 1=1 or name LIKE "'},
            user="Administrator")
        self.assertEqual(result["total_count"], 0)

    # ------------------------------------------------------------ scorecard

    def test_a_rating_parameter_needs_a_rating(self):
        demo = self._demo()
        with self.assertRaises(frappe.ValidationError):
            self._evaluation(demo, lines=[{"parameter": self.rating_param}])

    def test_a_measured_parameter_needs_a_value(self):
        demo = self._demo()
        with self.assertRaises(frappe.ValidationError):
            self._evaluation(demo, lines=[{"parameter": self.minutes_param}])

    def test_a_rating_against_a_measured_parameter_is_not_accepted(self):
        """The original stored both in untyped columns, so "Excellent minutes"
        was a thing that could be saved."""
        demo = self._demo()
        with self.assertRaises(frappe.ValidationError):
            self._evaluation(
                demo, lines=[{"parameter": self.minutes_param, "rating": "Excellent"}]
            )

    def test_a_measurement_against_a_rating_parameter_is_discarded(self):
        demo = self._demo()
        ev = self._evaluation(
            demo,
            lines=[{"parameter": self.rating_param, "rating": "Good", "value": 42}],
        )
        self.assertEqual(ev.parameters[0].value, 0)
        self.assertEqual(ev.parameters[0].rating, "Good")

    def test_a_measured_parameter_clears_any_rating(self):
        demo = self._demo()
        ev = self._evaluation(
            demo, lines=[{"parameter": self.minutes_param, "value": 45}]
        )
        self.assertEqual(ev.parameters[0].value, 45)
        self.assertIsNone(ev.parameters[0].rating)

    def test_a_parameter_that_requires_remarks_enforces_them(self):
        demo = self._demo()
        with self.assertRaises(frappe.ValidationError):
            self._evaluation(
                demo, lines=[{"parameter": self.remarks_param, "rating": "Fair"}]
            )
        ev = self._evaluation(
            demo,
            lines=[{"parameter": self.remarks_param, "rating": "Fair",
                    "remarks": "Sticky at high hydration"}],
        )
        self.assertEqual(ev.parameters[0].remarks, "Sticky at high hydration")

    def test_value_type_is_taken_from_the_parameter(self):
        demo = self._demo()
        ev = self._evaluation(
            demo, lines=[{"parameter": self.minutes_param, "value": 30}]
        )
        self.assertEqual(ev.parameters[0].value_type, "Minutes")

    # ------------------------------------------------------------ outcome

    def test_an_order_clears_the_no_order_reason(self):
        demo = self._demo()
        ev = self._evaluation(demo, order_received=1, no_order_reason="Price")
        self.assertIsNone(ev.no_order_reason)

    def test_an_unsuccessful_demo_needs_a_reason(self):
        demo = self._demo()
        with self.assertRaises(frappe.ValidationError):
            self._evaluation(demo, outcome="Unsuccessful", order_received=0,
                             no_order_reason=None)

    def test_evaluation_links_back_to_the_demo_line(self):
        demo = self._demo()
        ev = self._evaluation(demo)
        demo.reload()
        self.assertEqual(demo.items[0].evaluation, ev.name)

    # ------------------------------------------------------------ summary

    def test_summary_counts_outcomes(self):
        demo = self._demo()
        self._evaluation(demo, outcome="Successful", order_received=1)
        summary = summarise(demo.name)
        self.assertEqual(summary["evaluated"], 1)
        self.assertEqual(summary["successful"], 1)
        self.assertEqual(summary["orders"], 1)
        self.assertEqual(summary["success_rate"], 100.0)

    def test_summary_of_an_unevaluated_demo_is_empty_not_an_error(self):
        demo = self._demo()
        summary = summarise(demo.name)
        self.assertEqual(summary["evaluated"], 0)
        self.assertEqual(summary["success_rate"], 0.0)

    def test_evaluation_list_filters_by_demo(self):
        demo_a = self._demo()
        demo_b = self._demo()
        self._evaluation(demo_a)
        result = paginated_list(
            EVALUATION_CONFIG, form={"product_demo": demo_a.name}, user="Administrator")
        self.assertEqual(result["total_count"], 1)
        empty = paginated_list(
            EVALUATION_CONFIG, form={"product_demo": demo_b.name}, user="Administrator")
        self.assertEqual(empty["total_count"], 0)
