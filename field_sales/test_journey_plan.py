# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the Journey Plan write path."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from field_sales.api.journey_plan import (
    apply_journey_plan_action,
    create_journey_plan,
    journey_plan,
    journey_plan_actions,
    journey_plan_list,
    submit_journey_plan,
    update_journey_plan,
)

REP = "ravi.tsm@demo.local"
REP_TERRITORY = "Kolkata Area"
ASM = "asm.wftest@demo.local"
NSM = "nsm.wftest@demo.local"


def _grant_role_directly(user_email, role):
    """Add a role straight to a User's own roles table, bypassing whatever
    Role Profile it has - saving a User with role_profile_name set
    re-syncs .roles from that profile and would silently wipe a role not
    already on it (see the SE Role Profile cleanup this same fix grew out
    of), so this only ever touches a dedicated, profile-less test user."""
    if not frappe.db.exists("User", user_email):
        user = frappe.new_doc("User")
        user.update({
            "email": user_email, "first_name": user_email.split("@")[0],
            "send_welcome_email": 0, "role_profile_name": None,
        })
        user.append("roles", {"role": "Sales Executive App"})
        user.insert(ignore_permissions=True)
        emp = frappe.new_doc("Employee")
        emp.update({
            "employee_name": user_email.split("@")[0], "user_id": user_email,
            "status": "Active", "company": frappe.defaults.get_global_default("company"),
            "date_of_joining": frappe.utils.nowdate(), "date_of_birth": "1990-01-01",
            "gender": "Male",
        })
        emp.flags.ignore_mandatory = True
        emp.insert(ignore_permissions=True)
    user = frappe.get_doc("User", user_email)
    if not any(r.role == role for r in user.roles):
        user.append("roles", {"role": role})
        user.save(ignore_permissions=True)


def ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.new_doc(doctype)
    doc.update(values)
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


class TestJourneyPlan(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure("Territory", "FS Write Test Area", {
            "territory_name": "FS Write Test Area",
            "parent_territory": "All Territories", "is_group": 0,
        })
        ensure("Travel Mode", "Bike", {"mode_name": "Bike"})
        cls.employee = frappe.db.get_value("Employee", {"user_id": REP}, "name")
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()
        # Everything under test runs as an actual field rep: the endpoints
        # deliberately refuse to file a plan against a user with no linked
        # Employee, same as Field Visit.
        frappe.set_user(REP)

    def tearDown(self):
        frappe.set_user("Administrator")
        self._cleanup()
        frappe.db.rollback()

    def _cleanup(self):
        for name in frappe.get_all("Journey Plan", pluck="name"):
            doc = frappe.get_doc("Journey Plan", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Journey Plan", name, force=True, ignore_permissions=True)

    def _payload(self, **overrides):
        payload = {
            "visit_date": nowdate(),
            "nature_of_travel": "HQ",
            "remarks": "Kolkata loop",
            "trips": [{
                "travel_state_from": "West Bengal",
                "travel_from_district": "Kolkata",
                "travel_from_city": "Kolkata",
                "same_as_from_address": 0,
                "travel_to_state": "West Bengal",
                "travel_to_district": "Howrah",
                "travel_to_city": "Howrah",
                "mode_of_travel": "Bike",
                "primary_customer": "Test Customer A",
            }],
        }
        payload.update(overrides)
        return payload

    # ------------------------------------------------------------ create

    def test_create_returns_a_draft(self):
        result = create_journey_plan(**self._payload())
        self.assertTrue(result["name"].startswith("JP-"))
        self.assertEqual(result["docstatus"], 0)

    def test_create_forces_the_signed_in_users_own_employee(self):
        other = frappe.db.get_value(
            "Employee", {"name": ["!=", self.employee], "status": "Active"}, "name"
        )
        result = create_journey_plan(**self._payload(sales_person=other))
        doc = frappe.get_doc("Journey Plan", result["name"])
        self.assertNotEqual(
            doc.sales_person, other,
            "a client set the plan against somebody else's employee record",
        )

    def test_create_ignores_fields_the_client_may_not_set(self):
        result = create_journey_plan(**self._payload(
            workflow_state="Approved",
            docstatus=1,
            territory="FS Write Test Area",
        ))
        doc = frappe.get_doc("Journey Plan", result["name"])
        self.assertEqual(doc.docstatus, 0)

    def test_create_requires_at_least_one_trip(self):
        with self.assertRaises(frappe.ValidationError):
            create_journey_plan(**self._payload(trips=[]))

    def test_create_accepts_trip_rows(self):
        result = create_journey_plan(**self._payload())
        doc = frappe.get_doc("Journey Plan", result["name"])
        self.assertEqual(len(doc.trips), 1)
        self.assertEqual(doc.trips[0].mode_of_travel, "Bike")
        self.assertEqual(doc.trips[0].primary_customer, "Test Customer A")

    def test_trip_rows_drop_undeclared_keys(self):
        result = create_journey_plan(**self._payload(trips=[{
            "travel_from_city": "Kolkata",
            "mode_of_travel": "Bike",
            "field_visit": "some-other-doc",
        }]))
        doc = frappe.get_doc("Journey Plan", result["name"])
        self.assertFalse(hasattr(doc.trips[0], "field_visit_should_not_exist"))
        self.assertEqual(doc.trips[0].travel_from_city, "Kolkata")

    def test_same_as_from_address_copies_the_from_leg(self):
        result = create_journey_plan(**self._payload(trips=[{
            "travel_state_from": "West Bengal",
            "travel_from_district": "Kolkata",
            "travel_from_city": "Kolkata",
            "same_as_from_address": 1,
            "mode_of_travel": "Bike",
        }]))
        doc = frappe.get_doc("Journey Plan", result["name"])
        self.assertEqual(doc.trips[0].travel_to_city, "Kolkata")

    # ------------------------------------------------------------ list / detail

    def test_list_and_detail(self):
        result = create_journey_plan(**self._payload())
        listing = journey_plan_list()
        self.assertGreaterEqual(listing["total_count"], 1)
        names = [r["name"] for r in listing["records"]]
        self.assertIn(result["name"], names)

        detail = journey_plan(result["name"])
        self.assertEqual(detail["nature_of_travel"], "HQ")
        self.assertEqual(len(detail["trips"]), 1)

    # ------------------------------------------------------------ update

    def test_update_edits_a_pending_plan(self):
        name = create_journey_plan(**self._payload())["name"]
        update_journey_plan(name, remarks="Second pass")
        doc = frappe.get_doc("Journey Plan", name)
        self.assertEqual(doc.remarks, "Second pass")

    def test_update_refuses_a_submitted_plan(self):
        name = create_journey_plan(**self._payload())["name"]
        submit_journey_plan(name)
        with self.assertRaises(frappe.ValidationError):
            update_journey_plan(name, remarks="too late")

    # ------------------------------------------------------------ submit

    def test_submit_approves_the_plan(self):
        name = create_journey_plan(**self._payload())["name"]
        result = submit_journey_plan(name)
        self.assertEqual(result["docstatus"], 1)

    def test_submit_keeps_workflow_state_consistent(self):
        """Real production bug this guards against: a plan submitted this
        way used to leave workflow_state stuck at 'Pending' with
        docstatus=1 - Frappe's own apply_workflow can't act on a plan in
        that state later (throws 'Illegal Document Status'), which is
        exactly what happened to every plan submitted before the ASM/NSM
        workflow existed."""
        name = create_journey_plan(**self._payload())["name"]
        submit_journey_plan(name)
        doc = frappe.get_doc("Journey Plan", name)
        self.assertEqual(doc.workflow_state, "Approved")


class TestJourneyPlanApproval(FrappeTestCase):
    """The real ASM -> NSM approval workflow (Pending -> ASM Approved ->
    Approved, with Reject/revise branches) - see hooks.py's Workflow
    fixture and journey_plan.py's journey_plan_actions/
    apply_journey_plan_action for why this exists: a plan now only ever
    reaches docstatus 1 via an NSM's own Approve action, never by the rep
    submitting their own plan."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        ensure("Travel Mode", "Bike", {"mode_name": "Bike"})
        cls.employee = frappe.db.get_value("Employee", {"user_id": REP}, "name")
        _grant_role_directly(ASM, "Area Sales Manager")
        _grant_role_directly(NSM, "NSM")
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
        for name in frappe.get_all("Journey Plan", pluck="name"):
            doc = frappe.get_doc("Journey Plan", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Journey Plan", name, force=True, ignore_permissions=True)

    def _plan(self):
        doc = frappe.new_doc("Journey Plan")
        doc.update({"visit_date": nowdate(), "nature_of_travel": "HQ", "sales_person": self.employee})
        doc.append("trips", {"mode_of_travel": "Bike"})
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return doc

    def test_new_plan_starts_pending_and_docstatus_zero(self):
        doc = self._plan()
        self.assertEqual(doc.workflow_state, "Pending")
        self.assertEqual(doc.docstatus, 0)

    def test_rep_cannot_approve_their_own_plan(self):
        doc = self._plan()
        actions = journey_plan_actions(doc.name)
        self.assertNotIn("Approve", [a["action"] for a in actions])
        with self.assertRaises(frappe.ValidationError):
            apply_journey_plan_action(doc.name, "Approve")

    def test_asm_approve_moves_to_asm_approved_still_draft(self):
        doc = self._plan()
        frappe.set_user(ASM)
        result = apply_journey_plan_action(doc.name, "Approve")
        self.assertEqual(result["workflow_state"], "ASM Approved")
        self.assertEqual(result["docstatus"], 0, "ASM approval alone must not submit the plan")

    def test_nsm_approve_from_pending_submits_directly(self):
        doc = self._plan()
        frappe.set_user(NSM)
        result = apply_journey_plan_action(doc.name, "Approve")
        self.assertEqual(result["workflow_state"], "Approved")
        self.assertEqual(result["docstatus"], 1, "reaching Approved must submit the plan")

    def test_nsm_approve_after_asm_approved_submits(self):
        doc = self._plan()
        frappe.set_user(ASM)
        apply_journey_plan_action(doc.name, "Approve")
        frappe.set_user(NSM)
        result = apply_journey_plan_action(doc.name, "Approve")
        self.assertEqual(result["workflow_state"], "Approved")
        self.assertEqual(result["docstatus"], 1)

    def test_asm_reject_leaves_plan_a_draft(self):
        doc = self._plan()
        frappe.set_user(ASM)
        result = apply_journey_plan_action(doc.name, "Reject")
        self.assertEqual(result["workflow_state"], "Rejected")
        self.assertEqual(result["docstatus"], 0)

    def test_rep_can_revise_a_rejected_plan_back_to_pending(self):
        doc = self._plan()
        frappe.set_user(ASM)
        apply_journey_plan_action(doc.name, "Reject")
        frappe.set_user(REP)
        result = apply_journey_plan_action(doc.name, "Pending")
        self.assertEqual(result["workflow_state"], "Pending")

    def test_expense_claim_gate_only_opens_once_actually_approved(self):
        """The same docstatus==1 check Expense Claim's create_visit_expense_claim
        already uses - proving the workflow fix didn't just move the label
        around but actually satisfies that real downstream dependency."""
        from field_sales.api.expense_claim import create_visit_expense_claim

        doc = self._plan()
        frappe.set_user(ASM)
        apply_journey_plan_action(doc.name, "Approve")  # ASM Approved, still docstatus 0
        frappe.set_user(REP)
        with self.assertRaises(frappe.ValidationError):
            create_visit_expense_claim(doc.name, expenses=[{"expense_type": "x", "amount": 1}])

        frappe.set_user(NSM)
        apply_journey_plan_action(doc.name, "Approve")  # now Approved, docstatus 1
        doc.reload()
        self.assertEqual(doc.docstatus, 1)
