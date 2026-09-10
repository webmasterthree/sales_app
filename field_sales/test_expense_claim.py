# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for filing a visit expense claim against a Journey Plan -
api/expense_claim.py."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from field_sales.api.expense_claim import (
    create_visit_expense_claim,
    journey_plan_expense_status,
    submit_visit_expense_claim,
)

REP = "ravi.tsm@demo.local"
OTHER_REP = "priya.tsm@demo.local"
MANAGER = "ec.manager.wftest@demo.local"


def ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.new_doc(doctype)
    doc.update(values)
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_manager_user(email):
    if not frappe.db.exists("User", email):
        user = frappe.new_doc("User")
        user.update({
            "email": email, "first_name": email.split("@")[0],
            "send_welcome_email": 0, "role_profile_name": None,
        })
        user.insert(ignore_permissions=True)
    if not frappe.db.exists("Employee", {"user_id": email}):
        emp = frappe.new_doc("Employee")
        emp.update({
            "employee_name": email.split("@")[0], "user_id": email, "status": "Active",
            "company": frappe.defaults.get_global_default("company"),
            "date_of_joining": frappe.utils.nowdate(), "date_of_birth": "1990-01-01",
            "gender": "Male",
        })
        emp.flags.ignore_mandatory = True
        emp.insert(ignore_permissions=True)
    return frappe.db.get_value("Employee", {"user_id": email}, "name")


class TestExpenseClaim(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = frappe.db.get_value("Employee", {"user_id": REP, "status": "Active"}, "name")
        cls.other_employee = frappe.db.get_value(
            "Employee", {"user_id": OTHER_REP, "status": "Active"}, "name"
        )
        company = frappe.defaults.get_global_default("company")
        account = frappe.db.get_value(
            "Account", {"company": company, "is_group": 0, "root_type": "Expense"}, "name"
        )
        cls.expense_type = ensure(
            "Expense Claim Type", "FS Test Travel Expense",
            {
                "expense_type": "FS Test Travel Expense",
                "accounts": [{"company": company, "default_account": account}],
            },
        )
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
        frappe.db.sql("delete from `tabNotification Log` where document_type = %s", ("Expense Claim",))
        for name in frappe.get_all("Expense Claim", {"employee": self.employee}, pluck="name"):
            doc = frappe.get_doc("Expense Claim", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Expense Claim", name, force=True, ignore_permissions=True)
        for name in frappe.get_all("Journey Plan", {"sales_person": self.employee}, pluck="name"):
            if frappe.db.get_value("Journey Plan", name, "docstatus") == 1:
                frappe.db.set_value("Journey Plan", name, "docstatus", 0)
            frappe.delete_doc("Journey Plan", name, force=True, ignore_permissions=True)

    def _plan(self, docstatus=1, sales_person=None):
        doc = frappe.new_doc("Journey Plan")
        doc.update({
            "visit_date": nowdate(),
            "nature_of_travel": "EX-HQ",
            "sales_person": sales_person or self.employee,
        })
        doc.append("trips", {"mode_of_travel": "Bus"})
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        if docstatus == 1:
            frappe.db.set_value("Journey Plan", doc.name, "docstatus", 1)
            doc.reload()
        return doc

    def _expenses(self, **overrides):
        row = {
            "expense_type": self.expense_type,
            "expense_date": nowdate(),
            "amount": 350,
            "description": "Auto travel",
        }
        row.update(overrides)
        return [row]

    def test_create_links_the_claim_back_to_the_plan(self):
        plan = self._plan()
        result = create_visit_expense_claim(plan.name, expenses=self._expenses())
        doc = frappe.get_doc("Expense Claim", result["name"])
        self.assertEqual(doc.fs_journey_plan, plan.name)
        self.assertEqual(doc.employee, self.employee)
        self.assertEqual(doc.docstatus, 0)
        self.assertEqual(len(doc.expenses), 1)
        self.assertEqual(doc.expenses[0].amount, 350)

    def test_status_is_filed_right_after_create(self):
        plan = self._plan()
        result = create_visit_expense_claim(plan.name, expenses=self._expenses())
        status = journey_plan_expense_status(plan.name)
        self.assertEqual(status["expense_claim"], result["name"])
        self.assertEqual(status["expense_status"], "Filed")

    def test_status_reflects_approval(self):
        plan = self._plan()
        result = create_visit_expense_claim(plan.name, expenses=self._expenses())
        frappe.set_user("Administrator")
        frappe.db.set_value("Expense Claim", result["name"], "approval_status", "Approved")
        self.assertEqual(journey_plan_expense_status(plan.name)["expense_status"], "Approved")

    def test_status_reflects_rejection(self):
        plan = self._plan()
        result = create_visit_expense_claim(plan.name, expenses=self._expenses())
        frappe.set_user("Administrator")
        frappe.db.set_value("Expense Claim", result["name"], "approval_status", "Rejected")
        self.assertEqual(journey_plan_expense_status(plan.name)["expense_status"], "Rejected")

    def test_status_reflects_cancellation(self):
        """The real bug this design avoids: a stored Link field on Journey
        Plan pointing at the claim made Frappe refuse to ever cancel that
        claim (LinkExistsError) - status is computed live instead, so
        cancelling here has to work cleanly."""
        plan = self._plan()
        result = create_visit_expense_claim(plan.name, expenses=self._expenses())
        frappe.set_user("Administrator")
        claim = frappe.get_doc("Expense Claim", result["name"])
        claim.approval_status = "Approved"
        claim.save(ignore_permissions=True)
        claim.submit()
        claim.cancel()
        self.assertEqual(journey_plan_expense_status(plan.name)["expense_status"], "Cancelled")

    def test_status_is_none_with_no_claim_filed(self):
        plan = self._plan()
        status = journey_plan_expense_status(plan.name)
        self.assertIsNone(status["expense_claim"])
        self.assertIsNone(status["expense_status"])

    def test_journey_plan_endpoint_includes_expense_status(self):
        from field_sales.api.journey_plan import journey_plan as journey_plan_detail

        plan = self._plan()
        result = create_visit_expense_claim(plan.name, expenses=self._expenses())
        data = journey_plan_detail(plan.name)
        self.assertEqual(data["expense_claim"], result["name"])
        self.assertEqual(data["expense_status"], "Filed")

    def test_create_ignores_a_client_sent_employee(self):
        """Employee is always the signed-in user's own - never trusted from
        the client, same rule as every other create_* endpoint in this app."""
        plan = self._plan()
        result = create_visit_expense_claim(
            plan.name, employee=self.other_employee, expenses=self._expenses()
        )
        doc = frappe.get_doc("Expense Claim", result["name"])
        self.assertEqual(doc.employee, self.employee)

    def test_create_requires_at_least_one_expense(self):
        plan = self._plan()
        with self.assertRaises(frappe.ValidationError):
            create_visit_expense_claim(plan.name, expenses=[])

    def test_create_refuses_a_draft_plan(self):
        plan = self._plan(docstatus=0)
        with self.assertRaises(frappe.ValidationError):
            create_visit_expense_claim(plan.name, expenses=self._expenses())

    def test_create_refuses_someone_elses_plan(self):
        """A rep can't file an expense claim against a plan filed by a
        different rep."""
        if not self.other_employee:
            self.skipTest("priya.tsm@demo.local has no active Employee on this site")
        frappe.set_user("Administrator")
        plan = self._plan(sales_person=self.other_employee)
        frappe.set_user(REP)
        with self.assertRaises(frappe.PermissionError):
            create_visit_expense_claim(plan.name, expenses=self._expenses())

    def test_create_leaves_the_claim_as_a_draft(self):
        """create_visit_expense_claim never auto-submits - Expense Claim's
        own on_submit refuses while approval_status is still Draft, so the
        rep's action here has to stop at filing, not submitting."""
        plan = self._plan()
        result = create_visit_expense_claim(plan.name, expenses=self._expenses())
        self.assertEqual(result["docstatus"], 0)

    def test_submit_still_refuses_before_approval(self):
        plan = self._plan()
        result = create_visit_expense_claim(plan.name, expenses=self._expenses())
        with self.assertRaises(frappe.ValidationError):
            submit_visit_expense_claim(result["name"])

    def test_submit_moves_docstatus_to_one_once_approved(self):
        plan = self._plan()
        result = create_visit_expense_claim(plan.name, expenses=self._expenses())
        frappe.set_user("Administrator")
        frappe.db.set_value("Expense Claim", result["name"], "approval_status", "Approved")
        frappe.set_user(REP)
        submitted = submit_visit_expense_claim(result["name"])
        self.assertEqual(submitted["docstatus"], 1)

    # ------------------------------------------------------------ notifications

    def test_filing_notifies_the_reps_manager(self):
        manager_emp = _ensure_manager_user(MANAGER)
        original = frappe.db.get_value("Employee", self.employee, "reports_to")
        frappe.db.set_value("Employee", self.employee, "reports_to", manager_emp)
        try:
            plan = self._plan()
            result = create_visit_expense_claim(plan.name, expenses=self._expenses())
            self.assertTrue(frappe.db.exists("Notification Log", {
                "for_user": MANAGER, "document_type": "Expense Claim", "document_name": result["name"],
            }))
        finally:
            frappe.db.set_value("Employee", self.employee, "reports_to", original)

    def test_approval_notifies_the_rep(self):
        plan = self._plan()
        result = create_visit_expense_claim(plan.name, expenses=self._expenses())
        frappe.set_user("Administrator")
        doc = frappe.get_doc("Expense Claim", result["name"])
        doc.approval_status = "Approved"
        doc.save(ignore_permissions=True)
        self.assertTrue(frappe.db.exists("Notification Log", {
            "for_user": REP, "document_type": "Expense Claim", "document_name": result["name"],
        }))

    def test_a_plain_hr_expense_claim_is_never_notified(self):
        """fs_journey_plan only exists on a claim filed through this app's
        own flow - a normal HR-filed claim (no journey plan link) must not
        trigger a field_sales notification at all."""
        doc = frappe.new_doc("Expense Claim")
        doc.update({
            "employee": self.employee, "expense_approver": "Administrator",
            "posting_date": nowdate(),
        })
        doc.append("expenses", {
            "expense_type": self.expense_type, "expense_date": nowdate(), "amount": 100,
        })
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        self.assertFalse(frappe.db.exists("Notification Log", {
            "document_type": "Expense Claim", "document_name": doc.name,
        }))
