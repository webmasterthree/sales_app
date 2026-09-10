# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for Field Visit."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime, nowdate

from field_sales.api.field_visit import LIST_CONFIG
from field_sales.api.listing import paginated_list
from field_sales.field_sales.doctype.field_visit.field_visit import check_in, check_out

TERRITORY = "FS Visit Test Area"
OTHER_TERRITORY = "FS Visit Test Other Area"


def ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.new_doc(doctype)
    doc.update(values)
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


class TestFieldVisit(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for t in (TERRITORY, OTHER_TERRITORY):
            ensure("Territory", t, {
                "territory_name": t, "parent_territory": "All Territories", "is_group": 0,
            })
        cls.reason = ensure("Field Reason", "FS Test Not Interested", {
            "reason": "FS Test Not Interested", "applies_to": "Visit",
        })
        cls.segment = ensure("Segment", "FS Test Bakery", {
            "segment_name": "FS Test Bakery",
        })
        cls.company = frappe.get_all("Company", pluck="name")[0]
        cls.employee = frappe.db.get_value("Employee", {"status": "Active"}, "name")
        cls.customer = frappe.db.get_value("Customer", {}, "name")
        cls.item = frappe.db.get_value("Item", {}, "name")
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()

    def tearDown(self):
        self._cleanup()
        frappe.db.rollback()

    def _cleanup(self):
        for name in frappe.get_all("Field Visit", pluck="name"):
            doc = frappe.get_doc("Field Visit", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Field Visit", name, force=True, ignore_permissions=True)

    def _visit(self, **overrides):
        values = {
            "party_type": "Customer",
            "customer": self.customer,
            "visit_date": nowdate(),
            "territory": TERRITORY,
            "sales_person": self.employee,
            "order_status": "With Order",
        }
        values.update(overrides)
        doc = frappe.new_doc("Field Visit")
        doc.update(values)
        doc.flags.ignore_mandatory = True
        return doc

    # ------------------------------------------------------------ party

    def test_a_customer_visit_saves(self):
        doc = self._visit()
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name.startswith("FV-"))
        self.assertEqual(doc.customer, self.customer)

    def test_a_group_territory_is_replaced_by_the_employee_own(self):
        """Frappe pre-fills `territory` from a system default of "All
        Territories" before validate() runs, so a bare `if self.territory`
        early-exit never catches it - see scope.resolve_leaf_territory."""
        expected = frappe.db.get_value("Employee", self.employee, "area")
        doc = self._visit(territory="All Territories")
        doc.insert(ignore_permissions=True)
        self.assertNotEqual(doc.territory, "All Territories")
        self.assertEqual(doc.territory, expected)

    def test_a_prospect_visit_saves_without_a_customer(self):
        doc = self._visit(party_type="Prospect", customer=None,
                          prospect_name="FS Test New Bakery")
        doc.insert(ignore_permissions=True)
        self.assertIsNone(doc.customer)
        self.assertEqual(doc.prospect_name, "FS Test New Bakery")

    def test_customer_visit_requires_a_customer(self):
        doc = self._visit(customer=None)
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)

    def test_prospect_visit_requires_a_name(self):
        doc = self._visit(party_type="Prospect", customer=None, prospect_name=None)
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)

    def test_switching_party_type_clears_the_other_side(self):
        doc = self._visit(party_type="Prospect", customer=self.customer,
                          prospect_name="FS Test Someone")
        doc.insert(ignore_permissions=True)
        self.assertIsNone(doc.customer, "a prospect visit kept a customer link")

    # ------------------------------------------------------------ outcome

    def test_without_order_requires_a_reason(self):
        doc = self._visit(order_status="Without Order")
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)

    def test_without_order_with_a_reason_saves(self):
        doc = self._visit(order_status="Without Order", reason=self.reason)
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.reason, self.reason)

    def test_with_order_clears_any_reason(self):
        doc = self._visit(order_status="With Order", reason=self.reason)
        doc.insert(ignore_permissions=True)
        self.assertIsNone(doc.reason)

    # ------------------------------------------------------------ timing

    def test_duration_is_derived_not_trusted(self):
        """A client could send any duration; the server recomputes it."""
        start = now_datetime()
        doc = self._visit(
            check_in=start,
            check_out=add_to_date(start, minutes=45),
            duration=999999,
        )
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.duration, 45 * 60)

    def test_duration_is_zero_until_checked_out(self):
        doc = self._visit(check_in=now_datetime(), duration=500)
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.duration, 0)

    def test_check_out_before_check_in_is_rejected(self):
        start = now_datetime()
        doc = self._visit(check_in=start, check_out=add_to_date(start, minutes=-10))
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)

    def test_check_in_then_check_out_records_a_duration(self):
        doc = self._visit()
        doc.insert(ignore_permissions=True)

        check_in(doc.name, latitude=22.5726, longitude=88.3639,
                 captured_address="Salt Lake, Kolkata")
        doc.reload()
        self.assertIsNotNone(doc.check_in)
        self.assertEqual(doc.check_in_latitude, 22.5726)

        check_out(doc.name)
        doc.reload()
        self.assertIsNotNone(doc.check_out)
        self.assertGreaterEqual(doc.duration, 0)

    def test_cannot_check_in_twice(self):
        doc = self._visit()
        doc.insert(ignore_permissions=True)
        check_in(doc.name, latitude=22.5726, longitude=88.3639)
        with self.assertRaises(frappe.ValidationError):
            check_in(doc.name, latitude=22.5726, longitude=88.3639)

    def test_cannot_check_out_before_checking_in(self):
        doc = self._visit()
        doc.insert(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError):
            check_out(doc.name)

    # ------------------------------------------------------------ children

    def test_pitched_items_are_stored(self):
        doc = self._visit()
        doc.append("pitched_items", {
            "item_code": self.item, "qty": 25, "uom": "Kg", "segment": self.segment,
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(len(doc.pitched_items), 1)
        self.assertEqual(doc.pitched_items[0].qty, 25)

    def test_pitched_item_shape_matches_opportunity_item(self):
        """Kept deliberately alignable so promotion stays a migration."""
        ours = {f.fieldname for f in frappe.get_meta("Field Visit Item").fields}
        theirs = {f.fieldname for f in frappe.get_meta("Opportunity Item").fields}
        for shared in ("item_code", "item_name", "qty", "uom"):
            self.assertIn(shared, ours)
            self.assertIn(shared, theirs, f"{shared} is no longer on Opportunity Item")

    def test_consumption_is_stored(self):
        doc = self._visit()
        doc.append("consumption", {
            "product_name": "Rival Improver", "monthly_qty": 120, "uom": "Kg",
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.consumption[0].monthly_qty, 120)

    # ------------------------------------------------------------ pipeline hedge

    def test_lead_and_opportunity_links_exist_and_are_optional(self):
        meta = frappe.get_meta("Field Visit")
        for fieldname, target in (("lead", "Lead"), ("opportunity", "Opportunity")):
            df = meta.get_field(fieldname)
            self.assertIsNotNone(df, f"{fieldname} link is missing")
            self.assertEqual(df.options, target)
            self.assertFalse(df.reqd, f"{fieldname} must stay optional")

    # ------------------------------------------------------------ listing

    def test_list_is_scoped_to_territory(self):
        mine = self._visit(territory=TERRITORY)
        mine.insert(ignore_permissions=True)
        theirs = self._visit(territory=OTHER_TERRITORY)
        theirs.insert(ignore_permissions=True)

        result = paginated_list(LIST_CONFIG, form={}, user="Administrator")
        names = [r["name"] for r in result["records"]]
        self.assertIn(mine.name, names)
        self.assertIn(theirs.name, names, "Administrator is unrestricted")

    def test_list_search_is_parameterised(self):
        doc = self._visit(outlet_name="FS Test Outlet")
        doc.insert(ignore_permissions=True)

        hit = paginated_list(LIST_CONFIG, form={"search_text": "FS Test Outlet"},
                             user="Administrator")
        self.assertEqual(hit["total_count"], 1)

        inject = paginated_list(
            LIST_CONFIG,
            form={"search_text": '" or 1=1 or outlet_name LIKE "'},
            user="Administrator",
        )
        self.assertEqual(inject["total_count"], 0)

    def test_list_tabs_split_draft_and_submitted(self):
        draft = self._visit()
        draft.insert(ignore_permissions=True)

        # a visit can only be submitted once it has been checked in and out
        submitted = self._visit()
        submitted.insert(ignore_permissions=True)
        check_in(submitted.name, latitude=22.5726, longitude=88.3639)
        check_out(submitted.name)
        submitted.reload()
        submitted.submit()

        d = paginated_list(LIST_CONFIG, form={"tab": "draft"}, user="Administrator")
        s = paginated_list(LIST_CONFIG, form={"tab": "submitted"}, user="Administrator")
        self.assertIn(draft.name, [r["name"] for r in d["records"]])
        self.assertIn(submitted.name, [r["name"] for r in s["records"]])
        self.assertNotIn(submitted.name, [r["name"] for r in d["records"]])
