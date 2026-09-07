# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for Customer Onboarding."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from field_sales.api.listing import paginated_list
from field_sales.api.onboarding import (
    ONBOARDING_CONFIG,
    create_onboarding,
    submit_onboarding,
    update_onboarding,
)
from field_sales.field_sales.doctype.customer_onboarding.customer_onboarding import (
    approve_onboarding,
    reject_onboarding,
)

REP = "ravi.tsm@demo.local"
MANAGER = "arun.rsm@demo.local"
TERRITORY = "Kolkata Area"


def ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.new_doc(doctype)
    doc.update(values)
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


class TestCustomerOnboarding(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = frappe.db.get_value("Employee", {"user_id": REP}, "name")
        # give the RSM the manager role this flow requires
        manager = frappe.get_doc("User", MANAGER)
        if "Sales Manager" not in {r.role for r in manager.roles}:
            if not frappe.db.exists("Role", "Sales Manager"):
                frappe.get_doc({"doctype": "Role", "role_name": "Sales Manager"}).insert(
                    ignore_permissions=True
                )
            manager.append("roles", {"role": "Sales Manager"})
            manager.save(ignore_permissions=True)
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()
        self.address = self._address()

    def tearDown(self):
        frappe.set_user("Administrator")
        self._cleanup()
        frappe.db.rollback()

    def _cleanup(self):
        for name in frappe.get_all("Customer Onboarding", pluck="name"):
            doc = frappe.get_doc("Customer Onboarding", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Customer Onboarding", name, force=True, ignore_permissions=True)
        for name in frappe.get_all(
            "Customer", {"customer_name": ["like", "FS Onboard Test%"]}, pluck="name"
        ):
            frappe.delete_doc("Customer", name, force=True, ignore_permissions=True)
        for name in frappe.get_all(
            "Address", {"address_title": ["like", "FS Onboard Test%"]}, pluck="name"
        ):
            frappe.delete_doc("Address", name, force=True, ignore_permissions=True)

    def _address(self):
        doc = frappe.new_doc("Address")
        doc.update({
            "address_title": "FS Onboard Test Outlet", "address_type": "Billing",
            "address_line1": "1 Test Lane", "city": "Kolkata",
            "state": "West Bengal", "country": "India", "pincode": "700001",
            "district": frappe.db.get_value("District", {"district": "Kolkata"}, "name"),
        })
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return doc.name

    def _payload(self, **overrides):
        payload = {
            "customer_name": "FS Onboard Test Bakery",
            "business_type": "Registered",
            "gst_category": "Registered Regular",
            "gstin": "19ABCDE1234F1ZX",
            "location": self.address,
            "contact_number": "9830099999",
            "territory": TERRITORY,
            "documents": [{"document_type": "GST Certificate", "attachment": "/files/x.pdf"}],
        }
        payload.update(overrides)
        return payload

    def _draft(self, **overrides):
        frappe.set_user(REP)
        try:
            return create_onboarding(**self._payload(**overrides))
        finally:
            frappe.set_user("Administrator")

    def _submitted(self, **overrides):
        result = self._draft(**overrides)
        frappe.set_user(REP)
        try:
            submit_onboarding(result["name"])
        finally:
            frappe.set_user("Administrator")
        return result["name"]

    # ------------------------------------------------------------ create

    def test_a_draft_saves(self):
        result = self._draft()
        doc = frappe.get_doc("Customer Onboarding", result["name"])
        self.assertEqual(doc.status, "Pending")
        self.assertEqual(doc.sales_person, self.employee)

    def test_a_group_territory_is_replaced_by_the_employee_own(self):
        """Frappe pre-fills `territory` from a system default of "All
        Territories" before validate() runs, so a bare `if self.territory`
        early-exit never catches it - see scope.resolve_leaf_territory.

        Built and inserted directly (bypassing create_onboarding's permission
        check) because a restricted user can never reach validate() with this
        value in the first place: Ravi's own User Permission on Territory
        already refuses to create anything scoped outside his grant, "All
        Territories" included. The controller fix is defense in depth for
        callers not under that restriction - Administrator, or a manager
        filing on a rep's behalf - so that is what this exercises.
        """
        doc = frappe.new_doc("Customer Onboarding")
        doc.update(self._payload(territory="All Territories"))
        doc.sales_person = self.employee
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        self.assertNotEqual(doc.territory, "All Territories")
        self.assertEqual(doc.territory, TERRITORY)

    def test_a_group_customer_group_is_not_carried_onto_the_customer(self):
        name = self._submitted(customer_group="All Customer Groups")
        frappe.set_user(MANAGER)
        try:
            result = approve_onboarding(name)
        finally:
            frappe.set_user("Administrator")
        customer_group = frappe.db.get_value("Customer", result["customer"], "customer_group")
        self.assertNotEqual(customer_group, "All Customer Groups")
        self.assertFalse(frappe.db.get_value("Customer Group", customer_group, "is_group"))

    def test_registered_business_requires_a_gstin(self):
        with self.assertRaises(frappe.ValidationError):
            self._draft(gstin=None)

    def test_unregistered_business_clears_gst_fields(self):
        result = self._draft(business_type="Unregistered", gstin=None, gst_category=None)
        doc = frappe.get_doc("Customer Onboarding", result["name"])
        self.assertIsNone(doc.gstin)

    def test_credit_terms_require_a_period(self):
        with self.assertRaises(frappe.ValidationError):
            self._draft(**{"proposed_credit": "Credit"})

    # ------------------------------------------------------------ duplicates

    def test_a_second_pending_request_for_the_same_contact_is_refused(self):
        self._draft()
        with self.assertRaises(frappe.ValidationError):
            self._draft(customer_name="FS Onboard Test Bakery 2")

    def test_a_second_request_for_the_same_gstin_is_refused_even_with_a_different_phone(self):
        self._draft()
        with self.assertRaises(frappe.ValidationError):
            self._draft(contact_number="9830011111")

    def test_a_different_contact_and_gstin_is_not_a_duplicate(self):
        self._draft()
        # no exception
        self._draft(contact_number="9830011111", gstin="19ZZZZZ9999F1ZY")

    def test_a_rejected_request_does_not_block_a_refiled_one(self):
        """Rejection means that specific request was refused, not that the
        outlet can never be onboarded - the rep must be able to try again."""
        name = self._submitted()
        frappe.set_user(MANAGER)
        try:
            reject_onboarding(name, remarks="Missing documents")
        finally:
            frappe.set_user("Administrator")
        # no exception
        self._draft(customer_name="FS Onboard Test Bakery Retry")

    def test_a_cancelled_request_does_not_block_a_refiled_one(self):
        name = self._submitted()
        frappe.get_doc("Customer Onboarding", name).cancel()
        # no exception
        self._draft(customer_name="FS Onboard Test Bakery Again")

    def test_an_approved_request_still_counts_as_a_duplicate(self):
        """An approved KYC already has a live Customer - filing a fresh one
        for the same outlet is a mistake to surface immediately, not a
        second, orphaned Customer to create silently."""
        name = self._submitted()
        frappe.set_user(MANAGER)
        try:
            approve_onboarding(name)
        finally:
            frappe.set_user("Administrator")
        with self.assertRaises(frappe.ValidationError):
            self._draft(customer_name="FS Onboard Test Bakery Repeat")

    def test_editing_a_draft_in_place_is_not_its_own_duplicate(self):
        """Saving the same document again must not trip over itself."""
        result = self._draft()
        doc = frappe.get_doc("Customer Onboarding", result["name"])
        doc.decision_remarks = None  # no-op change, just forces another save
        doc.flags.ignore_permissions = True
        doc.save()  # no exception

    def test_client_cannot_set_status_or_customer_directly(self):
        frappe.set_user(REP)
        try:
            result = create_onboarding(**self._payload(status="Approved", customer="Fake"))
        finally:
            frappe.set_user("Administrator")
        doc = frappe.get_doc("Customer Onboarding", result["name"])
        self.assertEqual(doc.status, "Pending")
        self.assertIsNone(doc.customer)

    def test_submit_requires_a_document(self):
        result = self._draft(documents=[])
        frappe.set_user(REP)
        try:
            with self.assertRaises(frappe.ValidationError):
                submit_onboarding(result["name"])
        finally:
            frappe.set_user("Administrator")

    def test_cannot_edit_after_submit(self):
        name = self._submitted()
        frappe.set_user(REP)
        try:
            with self.assertRaises(frappe.ValidationError):
                update_onboarding(name, customer_name="tampered")
        finally:
            frappe.set_user("Administrator")

    # ------------------------------------------------------------ approval

    def test_a_rep_cannot_approve_their_own_request(self):
        name = self._submitted()
        frappe.set_user(REP)
        try:
            with self.assertRaises(frappe.PermissionError):
                approve_onboarding(name)
        finally:
            frappe.set_user("Administrator")

    def test_a_manager_can_approve(self):
        name = self._submitted()
        frappe.set_user(MANAGER)
        try:
            result = approve_onboarding(name)
        finally:
            frappe.set_user("Administrator")
        self.assertEqual(result["status"], "Approved")
        self.assertTrue(frappe.db.exists("Customer", result["customer"]))

    def test_approval_creates_a_real_customer_record(self):
        name = self._submitted()
        frappe.set_user(MANAGER)
        try:
            result = approve_onboarding(name)
        finally:
            frappe.set_user("Administrator")
        customer = frappe.get_doc("Customer", result["customer"])
        self.assertEqual(customer.customer_name, "FS Onboard Test Bakery")
        self.assertEqual(customer.mobile_no, "9830099999")
        self.assertEqual(customer.customer_primary_address, self.address)

    def test_approval_only_populates_fields_that_exist(self):
        """A clean install has none of mohan_impex's mandatory custom fields -
        approval must not assume any of them are there."""
        name = self._submitted()
        frappe.set_user(MANAGER)
        try:
            result = approve_onboarding(name)
        finally:
            frappe.set_user("Administrator")
        # did not raise even though this site's Customer has 6 legacy
        # mandatory custom fields this code never explicitly satisfies
        self.assertTrue(frappe.db.exists("Customer", result["customer"]))

    def test_cannot_approve_twice(self):
        name = self._submitted()
        frappe.set_user(MANAGER)
        try:
            approve_onboarding(name)
            with self.assertRaises(frappe.ValidationError):
                approve_onboarding(name)
        finally:
            frappe.set_user("Administrator")

    def test_cannot_approve_a_draft(self):
        result = self._draft()
        frappe.set_user(MANAGER)
        try:
            with self.assertRaises(frappe.ValidationError):
                approve_onboarding(result["name"])
        finally:
            frappe.set_user("Administrator")

    def test_rejection_requires_remarks(self):
        name = self._submitted()
        frappe.set_user(MANAGER)
        try:
            with self.assertRaises(frappe.ValidationError):
                reject_onboarding(name, remarks="   ")
        finally:
            frappe.set_user("Administrator")

    def test_rejection_does_not_create_a_customer(self):
        name = self._submitted()
        frappe.set_user(MANAGER)
        try:
            result = reject_onboarding(name, remarks="Duplicate outlet")
        finally:
            frappe.set_user("Administrator")
        self.assertEqual(result["status"], "Rejected")
        doc = frappe.get_doc("Customer Onboarding", name)
        self.assertIsNone(doc.customer)

    def test_a_rep_cannot_reject_either(self):
        name = self._submitted()
        frappe.set_user(REP)
        try:
            with self.assertRaises(frappe.PermissionError):
                reject_onboarding(name, remarks="no")
        finally:
            frappe.set_user("Administrator")

    # ------------------------------------------------------------ listing

    def test_list_tabs(self):
        pending = self._submitted()
        # Different contact_number AND gstin (a second, distinct, checksum-
        # valid GSTIN - approve_onboarding below builds a real Customer,
        # which india_compliance validates the checksum of) - these are
        # meant to be two distinct outlets for this test's purpose, and
        # validate_duplicate now blocks a second onboarding that shares
        # either identifier with an existing, still-active request.
        approved_name = self._submitted(
            customer_name="FS Onboard Test Approved",
            contact_number="9830099998",
            gstin="19ZZZZZ0000F1ZS",
        )
        frappe.set_user(MANAGER)
        try:
            approve_onboarding(approved_name)
        finally:
            frappe.set_user("Administrator")

        p = paginated_list(ONBOARDING_CONFIG, form={"tab": "pending"}, user="Administrator")
        a = paginated_list(ONBOARDING_CONFIG, form={"tab": "approved"}, user="Administrator")
        self.assertIn(pending, [r["name"] for r in p["records"]])
        self.assertIn(approved_name, [r["name"] for r in a["records"]])

    def test_list_is_territory_scoped(self):
        mine = self._draft(territory=TERRITORY)
        result = paginated_list(ONBOARDING_CONFIG, form={}, user=REP)
        self.assertIn(mine["name"], [r["name"] for r in result["records"]])

    def test_list_search_is_parameterised(self):
        self._draft()
        result = paginated_list(
            ONBOARDING_CONFIG,
            form={"search_text": '" or 1=1 or customer_name LIKE "'},
            user="Administrator",
        )
        self.assertEqual(result["total_count"], 0)
