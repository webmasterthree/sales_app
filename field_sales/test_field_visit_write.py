# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the Field Visit write path and geofencing."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from field_sales import geo
from field_sales.api.field_visit import create_visit, submit_visit, update_visit
from field_sales.field_sales.doctype.field_visit.field_visit import check_in, check_out

# Kolkata, and points a known distance away
OUTLET = (22.572600, 88.363900)
NEAR = (22.573100, 88.364200)      # ~63 m
FAR = (22.600000, 88.400000)       # ~4.5 km

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


class TestFieldVisitWrite(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure("Territory", "FS Write Test Area", {
            "territory_name": "FS Write Test Area",
            "parent_territory": "All Territories", "is_group": 0,
        })
        cls.reason = ensure("Field Reason", "FS Write Test Reason", {
            "reason": "FS Write Test Reason", "applies_to": "Visit",
        })
        cls.customer = frappe.db.get_value("Customer", {}, "name")
        cls.employee = frappe.db.get_value("Employee", {"status": "Active"}, "name")
        cls.item = frappe.db.get_value("Item", {}, "name")
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()
        self.address = self._address(with_position=True)
        self._settings(enforce=1, radius=200, behaviour="Warn", anchor=1)
        # Everything under test runs as an actual field rep: Administrator has
        # no Employee record, and the endpoints deliberately refuse to file a
        # visit against a user that is not linked to one.
        frappe.set_user(REP)

    def tearDown(self):
        frappe.set_user("Administrator")
        self._cleanup()
        frappe.db.rollback()

    def _cleanup(self):
        for name in frappe.get_all("Field Visit", pluck="name"):
            doc = frappe.get_doc("Field Visit", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Field Visit", name, force=True, ignore_permissions=True)
        for name in frappe.get_all("Address", {"address_title": ["like", "FS Write Test%"]}, pluck="name"):
            frappe.delete_doc("Address", name, force=True, ignore_permissions=True)

    def _address(self, with_position: bool):
        doc = frappe.new_doc("Address")
        doc.update({
            "address_title": "FS Write Test Outlet",
            "address_type": "Billing",
            "address_line1": "12 Demo Road",
            "city": "Kolkata",
            "country": "India",
            # india_compliance requires a state on an Indian address, and the
            # legacy app makes district mandatory too
            "state": "West Bengal",
            "district": frappe.db.get_value("District", {"district": "Kolkata"}, "name"),
            "pincode": "700001",
        })
        if with_position:
            doc.fs_latitude, doc.fs_longitude = OUTLET
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return doc.name

    def _settings(self, enforce=1, radius=200, behaviour="Warn", anchor=1):
        current = frappe.session.user
        frappe.set_user("Administrator")
        cfg = frappe.get_single("Field Sales Settings")
        cfg.enforce_geofence = enforce
        cfg.geofence_radius = radius
        cfg.geofence_behaviour = behaviour
        cfg.anchor_on_first_visit = anchor
        cfg.flags.ignore_mandatory = True
        cfg.save(ignore_permissions=True)
        frappe.clear_cache(doctype="Field Sales Settings")
        frappe.set_user(current)

    def _payload(self, **overrides):
        payload = {
            "party_type": "Customer",
            "customer": self.customer,
            "outlet_name": "FS Write Test Outlet",
            "visit_date": nowdate(),
            "location": self.address,
            "territory": REP_TERRITORY,
            "order_status": "With Order",
            "deal_confidence": "4",
        }
        payload.update(overrides)
        return payload

    # ------------------------------------------------------------ distance

    def test_haversine_matches_a_known_distance(self):
        """Kolkata to Delhi is about 1305 km great-circle."""
        d = geo.haversine_metres(22.5726, 88.3639, 28.6139, 77.2090)
        self.assertAlmostEqual(d / 1000.0, 1305, delta=15)

    def test_haversine_is_zero_for_the_same_point(self):
        self.assertEqual(geo.haversine_metres(22.5726, 88.3639, 22.5726, 88.3639), 0.0)

    def test_null_island_is_not_a_valid_fix(self):
        self.assertFalse(geo.is_valid_position(0, 0))
        self.assertFalse(geo.is_valid_position(None, None))
        self.assertFalse(geo.is_valid_position(91, 0))
        self.assertTrue(geo.is_valid_position(*OUTLET))

    # ------------------------------------------------------------ create

    def test_create_returns_a_draft(self):
        result = create_visit(**self._payload())
        self.assertTrue(result["name"].startswith("FV-"))
        self.assertEqual(result["docstatus"], 0)

    def test_create_ignores_fields_the_client_may_not_set(self):
        """The client cannot decide the duration, the timestamps or the verdict."""
        result = create_visit(**self._payload(
            duration=999999,
            check_in="2020-01-01 09:00:00",
            check_out="2020-01-01 18:00:00",
            geofence_status="Inside",
            check_in_distance=0,
            docstatus=1,
        ))
        doc = frappe.get_doc("Field Visit", result["name"])
        self.assertEqual(doc.duration, 0)
        self.assertIsNone(doc.check_in)
        self.assertIsNone(doc.check_out)
        self.assertIn(doc.geofence_status, (None, ""))
        self.assertEqual(doc.docstatus, 0)

    def test_create_forces_the_signed_in_users_own_employee(self):
        other = frappe.db.get_value(
            "Employee", {"name": ["!=", self.employee], "status": "Active"}, "name"
        )
        result = create_visit(**self._payload(sales_person=other))
        doc = frappe.get_doc("Field Visit", result["name"])
        self.assertNotEqual(
            doc.sales_person, other,
            "a client set the visit against somebody else's employee record",
        )

    def test_create_accepts_child_rows(self):
        result = create_visit(**self._payload(
            pitched_items=[{"item_code": self.item, "qty": 12, "uom": "Kg"}],
            consumption=[{"product_name": "Rival brand", "monthly_qty": 90}],
        ))
        doc = frappe.get_doc("Field Visit", result["name"])
        self.assertEqual(len(doc.pitched_items), 1)
        self.assertEqual(doc.pitched_items[0].qty, 12)
        self.assertEqual(doc.consumption[0].monthly_qty, 90)

    def test_child_rows_drop_undeclared_keys(self):
        result = create_visit(**self._payload(
            pitched_items=[{"item_code": self.item, "qty": 5, "rate": 999999}],
        ))
        doc = frappe.get_doc("Field Visit", result["name"])
        self.assertEqual(doc.pitched_items[0].qty, 5)

    # ------------------------------------------------------------ update

    def test_update_edits_a_draft(self):
        name = create_visit(**self._payload())["name"]
        update_visit(name, remarks="Second pass", deal_confidence="2")
        doc = frappe.get_doc("Field Visit", name)
        self.assertEqual(doc.remarks, "Second pass")
        self.assertEqual(doc.deal_confidence, "2")

    def test_update_refuses_a_submitted_visit(self):
        name = self._complete_visit()
        submit_visit(name)
        with self.assertRaises(frappe.ValidationError):
            update_visit(name, remarks="too late")

    # ------------------------------------------------------------ check in

    def test_check_in_inside_the_radius(self):
        name = create_visit(**self._payload())["name"]
        result = check_in(name, latitude=NEAR[0], longitude=NEAR[1])
        self.assertEqual(result["geofence"], "Inside")
        self.assertLess(result["distance"], 200)

    def test_check_in_outside_the_radius_is_recorded_when_warning(self):
        self._settings(behaviour="Warn")
        name = create_visit(**self._payload())["name"]
        result = check_in(name, latitude=FAR[0], longitude=FAR[1])
        self.assertEqual(result["geofence"], "Outside")
        self.assertGreater(result["distance"], 200)
        doc = frappe.get_doc("Field Visit", name)
        self.assertIsNotNone(doc.check_in, "Warn must still let the visit proceed")

    def test_check_in_outside_the_radius_is_refused_when_blocking(self):
        self._settings(behaviour="Block")
        name = create_visit(**self._payload())["name"]
        with self.assertRaises(frappe.ValidationError):
            check_in(name, latitude=FAR[0], longitude=FAR[1])
        doc = frappe.get_doc("Field Visit", name)
        self.assertIsNone(doc.check_in)

    def test_a_missing_fix_is_not_checked_rather_than_inside(self):
        """Failing to send coordinates must not read as being at the outlet."""
        name = create_visit(**self._payload())["name"]
        result = check_in(name)
        self.assertEqual(result["geofence"], "Not Checked")
        self.assertIsNone(result["distance"])

    def test_null_island_is_not_checked(self):
        name = create_visit(**self._payload())["name"]
        result = check_in(name, latitude=0, longitude=0)
        self.assertEqual(result["geofence"], "Not Checked")

    def test_first_visit_anchors_an_outlet_with_no_position(self):
        blank = frappe.get_doc("Address", self.address)
        blank.fs_latitude = 0
        blank.fs_longitude = 0
        blank.save(ignore_permissions=True)

        name = create_visit(**self._payload())["name"]
        result = check_in(name, latitude=NEAR[0], longitude=NEAR[1])
        self.assertEqual(result["geofence"], "Inside")

        stored = frappe.db.get_value(
            "Address", self.address, ["fs_latitude", "fs_longitude"], as_dict=True
        )
        self.assertAlmostEqual(stored.fs_latitude, NEAR[0], places=4)

    def test_geofence_can_be_switched_off(self):
        self._settings(enforce=0)
        name = create_visit(**self._payload())["name"]
        result = check_in(name, latitude=FAR[0], longitude=FAR[1])
        self.assertEqual(result["geofence"], "Not Checked")

    def test_cannot_check_in_twice(self):
        name = create_visit(**self._payload())["name"]
        check_in(name, latitude=NEAR[0], longitude=NEAR[1])
        with self.assertRaises(frappe.ValidationError):
            check_in(name, latitude=NEAR[0], longitude=NEAR[1])

    # ------------------------------------------------------------ check out

    def test_check_out_records_a_duration(self):
        name = self._complete_visit()
        doc = frappe.get_doc("Field Visit", name)
        self.assertIsNotNone(doc.check_out)
        self.assertGreaterEqual(doc.duration, 0)

    def test_cannot_check_out_first(self):
        name = create_visit(**self._payload())["name"]
        with self.assertRaises(frappe.ValidationError):
            check_out(name)

    # ------------------------------------------------------------ submit

    def test_submit_requires_check_in_and_out(self):
        name = create_visit(**self._payload())["name"]
        with self.assertRaises(frappe.ValidationError):
            submit_visit(name)

    def test_submit_after_a_complete_visit(self):
        name = self._complete_visit()
        result = submit_visit(name)
        self.assertEqual(result["docstatus"], 1)

    def test_check_in_refused_once_submitted(self):
        name = self._complete_visit()
        submit_visit(name)
        with self.assertRaises(frappe.ValidationError):
            check_out(name)

    # ------------------------------------------------------------ helper

    def _complete_visit(self) -> str:
        name = create_visit(**self._payload())["name"]
        check_in(name, latitude=NEAR[0], longitude=NEAR[1])
        check_out(name, latitude=NEAR[0], longitude=NEAR[1])
        return name
