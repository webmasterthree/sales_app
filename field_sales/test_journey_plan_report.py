# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for journey_plan_visit_report - correlates a Journey Plan with the
Field Visit(s) its rep actually logged the same day, including
geolocation."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from field_sales.api.journey_plan import journey_plan_visit_report

REP = "ravi.tsm@demo.local"
OTHER_REP = "priya.tsm@demo.local"


def ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.new_doc(doctype)
    doc.update(values)
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


class TestJourneyPlanVisitReport(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = frappe.db.get_value("Employee", {"user_id": REP, "status": "Active"}, "name")
        cls.other_employee = frappe.db.get_value(
            "Employee", {"user_id": OTHER_REP, "status": "Active"}, "name"
        )
        cls.customer = ensure("Customer", "FS Test JP Report Customer", {
            "customer_name": "FS Test JP Report Customer",
            "customer_group": "Commercial", "territory": "Kolkata Area",
        })

    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()

    def tearDown(self):
        self._cleanup()
        frappe.db.rollback()

    def _cleanup(self):
        for name in frappe.get_all("Field Visit", {"customer": self.customer}, pluck="name"):
            if frappe.db.get_value("Field Visit", name, "docstatus") == 1:
                frappe.db.set_value("Field Visit", name, "docstatus", 0)
            frappe.delete_doc("Field Visit", name, force=True, ignore_permissions=True)
        for emp in (self.employee, self.other_employee):
            if not emp:
                continue
            for name in frappe.get_all("Journey Plan", {"sales_person": emp}, pluck="name"):
                if frappe.db.get_value("Journey Plan", name, "docstatus") == 1:
                    frappe.db.set_value("Journey Plan", name, "docstatus", 0)
                frappe.delete_doc("Journey Plan", name, force=True, ignore_permissions=True)

    def _plan(self, sales_person=None, visit_date=None):
        doc = frappe.new_doc("Journey Plan")
        doc.update({
            "visit_date": visit_date or nowdate(),
            "nature_of_travel": "EX-HQ",
            "sales_person": sales_person or self.employee,
        })
        doc.append("trips", {"mode_of_travel": "Bus"})
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        frappe.db.set_value("Journey Plan", doc.name, "docstatus", 1)
        return doc

    def _visit(self, sales_person=None, visit_date=None, lat=22.5726, lng=88.3639):
        doc = frappe.new_doc("Field Visit")
        doc.update({
            "party_type": "Customer",
            "customer": self.customer,
            "visit_date": visit_date or nowdate(),
            "order_status": "With Order",
            "sales_person": sales_person or self.employee,
            "check_in_latitude": lat,
            "check_in_longitude": lng,
            "geofence_status": "Inside",
        })
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        frappe.db.set_value("Field Visit", doc.name, "docstatus", 1)
        return doc

    def test_report_pairs_a_plan_with_its_own_days_visit(self):
        plan = self._plan()
        visit = self._visit()
        rows = journey_plan_visit_report(nowdate())
        row = next(r for r in rows if r["name"] == plan.name)
        self.assertEqual(len(row["visits"]), 1)
        self.assertEqual(row["visits"][0]["name"], visit.name)
        self.assertEqual(row["visits"][0]["check_in_latitude"], 22.5726)
        self.assertEqual(row["visits"][0]["check_in_longitude"], 88.3639)
        self.assertEqual(row["visits"][0]["geofence_status"], "Inside")

    def test_report_shows_a_plan_with_no_visit_yet(self):
        plan = self._plan()
        rows = journey_plan_visit_report(nowdate())
        row = next(r for r in rows if r["name"] == plan.name)
        self.assertEqual(row["visits"], [])

    def test_report_surfaces_an_unplanned_visit(self):
        """A rep who logged a visit with no journey plan filed still shows
        up - as their own group, not silently dropped."""
        visit = self._visit()
        rows = journey_plan_visit_report(nowdate())
        row = next(r for r in rows if r["name"] is None and r["sales_person"] == self.employee)
        self.assertEqual(len(row["visits"]), 1)
        self.assertEqual(row["visits"][0]["name"], visit.name)

    def test_report_ignores_a_different_days_visit(self):
        plan = self._plan()
        self._visit(visit_date="2020-01-01")
        rows = journey_plan_visit_report(nowdate())
        row = next(r for r in rows if r["name"] == plan.name)
        self.assertEqual(row["visits"], [])

    def test_report_keeps_each_reps_visits_separate(self):
        if not self.other_employee:
            self.skipTest("priya.tsm@demo.local has no active Employee on this site")
        plan_a = self._plan(sales_person=self.employee)
        plan_b = self._plan(sales_person=self.other_employee)
        visit_a = self._visit(sales_person=self.employee)
        visit_b = self._visit(sales_person=self.other_employee, lat=12.9716, lng=77.5946)

        rows = journey_plan_visit_report(nowdate())
        row_a = next(r for r in rows if r["name"] == plan_a.name)
        row_b = next(r for r in rows if r["name"] == plan_b.name)
        self.assertEqual([v["name"] for v in row_a["visits"]], [visit_a.name])
        self.assertEqual([v["name"] for v in row_b["visits"]], [visit_b.name])
