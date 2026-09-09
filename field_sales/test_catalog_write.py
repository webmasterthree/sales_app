# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the Sales Order write path in api/catalog.py.

field_sales.test_pricing already covers enforce_sales_order_rates as a unit -
calling it directly against a bare frappe.new_doc("Sales Order"). These tests
cover the thing that unit test cannot: that the whitelisted create_order/
update_order/submit_order endpoints, exercising the real insert/save/submit
lifecycle, still end up with the server's own rate on disk even when a client
sends a different one - the actual defect this app existed to close.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate

from field_sales.api.catalog import _resolve_gst, create_order, order_list, submit_order, update_order

REP = "ravi.tsm@demo.local"
PRICE_LIST = "Standard Selling"
LIST_RATE = 640.0


def ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.new_doc(doctype)
    doc.update(values)
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


class TestSalesOrderWrite(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = frappe.db.get_value(
            "Employee", {"user_id": REP, "status": "Active"}, "name"
        )

        cls.item = "FS-TEST-CATALOG-ITEM-001"
        if not frappe.db.exists("Item", cls.item):
            hsn = frappe.get_all("GST HSN Code", limit=1, pluck="name")
            cat = frappe.get_all("Item Category", limit=1, pluck="name")
            doc = frappe.new_doc("Item")
            doc.update({
                "item_code": cls.item, "item_name": "FS Test Catalog Item",
                "item_group": "All Item Groups", "stock_uom": "Kg",
                "is_stock_item": 0, "is_sales_item": 1,
            })
            if hsn:
                doc.gst_hsn_code = hsn[0]
            if cat:
                doc.item_category = cat[0]
            doc.flags.ignore_mandatory = True
            doc.insert(ignore_permissions=True)

        cls.customer = "FS Test Catalog Customer"
        if not frappe.db.exists("Customer", {"customer_name": cls.customer}):
            doc = frappe.new_doc("Customer")
            doc.update({
                "customer_name": cls.customer, "customer_type": "Company",
                "customer_group": "Commercial", "territory": "Kolkata Area",
                "business_type": "Registered", "gst_category": "Registered Regular",
            })
            doc.flags.ignore_mandatory = True
            doc.insert(ignore_permissions=True)
        cls.customer = frappe.db.get_value(
            "Customer", {"customer_name": cls.customer}, "name"
        )

        shop = frappe.get_all("Shop", limit=1, pluck="name")
        cls.shop = shop[0] if shop else None
        frappe.db.set_value("Customer", cls.customer, "custom_shop", cls.shop)
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._clear_prices()
        self._price(LIST_RATE)
        self._cleanup()
        frappe.set_user(REP)

    def tearDown(self):
        frappe.set_user("Administrator")
        self._cleanup()
        self._clear_prices()
        frappe.db.rollback()

    def _clear_prices(self):
        for name in frappe.get_all("Item Price", {"item_code": self.item}, pluck="name"):
            frappe.delete_doc("Item Price", name, force=True, ignore_permissions=True)

    def _price(self, rate):
        doc = frappe.new_doc("Item Price")
        doc.update({
            "item_code": self.item, "price_list": PRICE_LIST,
            "price_list_rate": rate, "uom": "Kg", "currency": "INR",
        })
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return doc.name

    def _cleanup(self):
        for name in frappe.get_all(
            "Sales Order", {"customer": self.customer}, pluck="name"
        ):
            doc = frappe.get_doc("Sales Order", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Sales Order", name, force=True, ignore_permissions=True)

    def _payload(self, rate=None, **overrides):
        payload = {
            "customer": self.customer,
            "delivery_date": add_days(nowdate(), 7),
            "items": [{
                "item_code": self.item, "qty": 10, "uom": "Kg",
                "rate": rate if rate is not None else 1,
                "amount": 999999,
                "price_list_rate": 1,
            }],
        }
        payload.update(overrides)
        return payload

    # ------------------------------------------------------------ create

    def test_create_returns_a_draft(self):
        result = create_order(**self._payload())
        self.assertTrue(result["name"])
        self.assertEqual(result["docstatus"], 0)

    def test_create_derives_contact_mobile_from_the_contact_person(self):
        """Real gap found while wiring up a WhatsApp order-confirmation
        notification: contact_mobile has no fetch_from of its own on this
        doctype, so it silently stayed blank on every order ever created
        here regardless of which contact was picked - breaking anything
        that reads it."""
        contact_name = ensure("Contact", "FS Test Catalog Contact", {
            "first_name": "FS Test Catalog Contact",
            "phone_nos": [{"phone": "+919876500000", "is_primary_mobile_no": 1}],
        })
        if not frappe.db.exists(
            "Dynamic Link", {"parent": contact_name, "link_doctype": "Customer", "link_name": self.customer}
        ):
            contact = frappe.get_doc("Contact", contact_name)
            contact.append("links", {"link_doctype": "Customer", "link_name": self.customer})
            contact.save(ignore_permissions=True)

        result = create_order(**self._payload(contact_person=contact_name))
        doc = frappe.get_doc("Sales Order", result["name"])
        self.assertEqual(doc.contact_mobile, "+919876500000")

    def test_ensure_contact_mobile_falls_back_to_customer_when_created_in_desk(self):
        """Real production bug: a Sales Order created directly in Desk never
        goes through create_order/_resolve_order_context at all, so it could
        reach submission with no contact_mobile whatsoever even though the
        Customer's own record has one - silently breaking anything that
        reads it (a WhatsApp order confirmation included). This is the
        universal doc_event fallback that covers that path too."""
        frappe.set_user("Administrator")
        frappe.db.set_value("Customer", self.customer, "mobile_no", "+919876511111")
        doc = frappe.new_doc("Sales Order")
        doc.customer = self.customer
        doc.company = frappe.defaults.get_global_default("company")
        doc.delivery_date = add_days(nowdate(), 7)
        doc.append("items", {"item_code": self.item, "qty": 1, "rate": LIST_RATE})
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.contact_mobile, "+919876511111")

    def test_ensure_contact_mobile_does_not_override_an_explicit_value(self):
        frappe.set_user("Administrator")
        doc = frappe.new_doc("Sales Order")
        doc.customer = self.customer
        doc.company = frappe.defaults.get_global_default("company")
        doc.delivery_date = add_days(nowdate(), 7)
        doc.contact_mobile = "+919876522222"
        doc.append("items", {"item_code": self.item, "qty": 1, "rate": LIST_RATE})
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.contact_mobile, "+919876522222")

    def test_a_client_supplied_rate_is_not_stored(self):
        """The headline defect: a client could name its own order price."""
        result = create_order(**self._payload(rate=1))
        doc = frappe.get_doc("Sales Order", result["name"])
        self.assertEqual(flt(doc.items[0].rate, 2), LIST_RATE)
        self.assertNotEqual(flt(doc.items[0].rate, 2), 1.0)

    def test_stored_rate_matches_what_item_price_would_quote(self):
        """What the app shows in step two must be what the order stores."""
        from field_sales.api.catalog import item_price

        quoted = item_price(item_code=self.item, customer=self.customer, qty=10)
        result = create_order(**self._payload(rate=1))
        doc = frappe.get_doc("Sales Order", result["name"])
        self.assertEqual(flt(doc.items[0].rate, 2), flt(quoted["final_rate"], 2))

    def test_client_cannot_set_amount_or_price_list_rate_directly(self):
        result = create_order(**self._payload(rate=1))
        doc = frappe.get_doc("Sales Order", result["name"])
        self.assertNotEqual(flt(doc.items[0].amount, 2), 999999.0)

    def test_create_forces_the_signed_in_users_own_employee(self):
        result = create_order(**self._payload())
        doc = frappe.get_doc("Sales Order", result["name"])
        if doc.meta.has_field("created_by_emp"):
            self.assertEqual(doc.created_by_emp, self.employee)

    def test_create_derives_shop_from_the_customer(self):
        result = create_order(**self._payload())
        doc = frappe.get_doc("Sales Order", result["name"])
        self.assertEqual(doc.shop, self.shop)

    def test_create_ignores_a_client_sent_shop(self):
        other = frappe.get_all(
            "Shop", filters={"name": ["!=", self.shop]}, limit=1, pluck="name"
        )
        if not other:
            self.skipTest("only one Shop on this site")
        result = create_order(**self._payload(shop=other[0]))
        doc = frappe.get_doc("Sales Order", result["name"])
        self.assertEqual(doc.shop, self.shop)

    def test_create_requires_a_customer(self):
        with self.assertRaises(frappe.ValidationError):
            create_order(delivery_date=add_days(nowdate(), 7), items=[
                {"item_code": self.item, "qty": 1, "uom": "Kg"}
            ])

    # ------------------------------------------------------------ channel partner

    def test_customer_type_is_derived_from_the_customer_not_the_client(self):
        """Same derivation as field_visit.py/field_trial_plan.py - a client
        claiming Secondary for a Primary customer is simply overridden."""
        result = create_order(**self._payload(customer_level="Secondary", custom_channel_partner="bogus"))
        doc = frappe.get_doc("Sales Order", result["name"])
        if not doc.meta.has_field("customer_level"):
            self.skipTest("customer_level not installed on this site's Sales Order")
        self.assertEqual(doc.customer_level, "Primary")
        self.assertFalse(doc.custom_channel_partner)

    def test_a_secondary_customers_channel_partner_is_copied_onto_the_order(self):
        partner = frappe.db.get_value("Customer", {"name": ["!=", self.customer]}, "name")
        if not partner:
            self.skipTest("need a second Customer on this site")
        doc = frappe.get_doc("Customer", self.customer)
        if not doc.meta.has_field("customer_level"):
            self.skipTest("customer_level not installed on this site's Customer")
        frappe.db.set_value(
            "Customer", self.customer,
            {"customer_level": "Secondary", "custom_channel_partner": partner},
        )
        try:
            result = create_order(**self._payload())
            order = frappe.get_doc("Sales Order", result["name"])
            self.assertEqual(order.customer_level, "Secondary")
            self.assertEqual(order.custom_channel_partner, partner)
        finally:
            frappe.db.set_value(
                "Customer", self.customer,
                {"customer_level": "Primary", "custom_channel_partner": None},
            )

    # ------------------------------------------------------------ update / submit

    def test_update_edits_a_draft(self):
        name = create_order(**self._payload())["name"]
        update_order(name, remarks="Second pass")
        doc = frappe.get_doc("Sales Order", name)
        self.assertEqual(doc.remarks, "Second pass")

    def test_update_recomputes_rate_after_a_client_edit(self):
        name = create_order(**self._payload())["name"]
        update_order(name, items=[{
            "item_code": self.item, "qty": 20, "uom": "Kg", "rate": 1,
        }])
        doc = frappe.get_doc("Sales Order", name)
        self.assertEqual(flt(doc.items[0].rate, 2), LIST_RATE)

    def test_update_refuses_a_submitted_order(self):
        name = create_order(**self._payload())["name"]
        submit_order(name)
        with self.assertRaises(frappe.ValidationError):
            update_order(name, remarks="too late")

    def test_submit_moves_docstatus_to_one(self):
        name = create_order(**self._payload())["name"]
        result = submit_order(name)
        self.assertEqual(result["docstatus"], 1)

    def test_submit_notifies_the_reps_manager(self):
        # Sales Order's on_submit hook (field_sales.notify.notify_sales_order_submitted,
        # wired in hooks.py) - this pins that it actually fires on a real
        # submit, not just in notify.py's own unit tests.
        original_manager = frappe.db.get_value("Employee", self.employee, "reports_to")
        manager_user = frappe.db.get_value("Employee", {"status": "Active", "user_id": ["!=", REP]}, "user_id")
        self.assertTrue(manager_user, "need a second active Employee with a user_id to act as manager")
        frappe.db.set_value("Employee", self.employee, "reports_to",
                             frappe.db.get_value("Employee", {"user_id": manager_user}, "name"))
        try:
            name = create_order(**self._payload())["name"]
            submit_order(name)
            self.assertTrue(
                frappe.db.exists("Notification Log", {
                    "for_user": manager_user, "document_type": "Sales Order", "document_name": name,
                })
            )
        finally:
            frappe.db.set_value("Employee", self.employee, "reports_to", original_manager)

    # ------------------------------------------------------------ gst
    #
    # Confirmed on production: india_compliance's get_gst_details silently
    # refuses to resolve any tax template at all - not even a blank one -
    # unless doc.company_gstin is already set. The Desk form's own JS fills
    # that field in the moment a company/warehouse is picked; a document
    # built by this endpoint never goes through that trigger, so the field
    # stayed blank and get_gst_details returned nothing but place_of_supply.
    # Every item then got stamped Nil-Rated by india_compliance's own
    # fallback for "no GST taxes on this doc", zeroing the whole order's tax
    # regardless of what each item's own Item Tax Template says. This site's
    # demo Company has no GSTIN, so get_gst_details itself is a real no-op
    # here (already covered by every other test in this file passing) -
    # these tests mock it to prove _resolve_gst's own wiring is correct
    # independent of that master data.

    def test_resolve_gst_fills_company_gstin_before_resolving(self):
        doc = frappe.new_doc("Sales Order")
        doc.company = frappe.defaults.get_global_default("company")
        captured = {}

        def fake_get_gst_details(party_details, doctype, company, update_place_of_supply=False):
            captured["company_gstin"] = party_details.get("company_gstin")
            return {}

        with (
            patch(
                "india_compliance.gst_india.overrides.transaction.get_gst_details",
                side_effect=fake_get_gst_details,
            ),
            patch("frappe.get_cached_value", return_value="19AATCM1676J1ZP"),
        ):
            _resolve_gst(doc)

        self.assertEqual(doc.company_gstin, "19AATCM1676J1ZP")
        self.assertEqual(captured["company_gstin"], "19AATCM1676J1ZP")

    def test_resolve_gst_applies_a_resolved_template_and_its_tax_rows(self):
        doc = frappe.new_doc("Sales Order")
        doc.company = frappe.defaults.get_global_default("company")
        fake_gst = {
            "place_of_supply": "09-Uttar Pradesh",
            "taxes_and_charges": "Fake Out-state GST Template",
            "taxes": [{
                "charge_type": "On Net Total", "account_head": "Fake IGST Account",
                "description": "IGST", "rate": 18,
            }],
        }
        with patch(
            "india_compliance.gst_india.overrides.transaction.get_gst_details",
            return_value=fake_gst,
        ):
            _resolve_gst(doc)
        self.assertEqual(doc.taxes_and_charges, "Fake Out-state GST Template")
        self.assertEqual(len(doc.taxes), 1)
        self.assertEqual(doc.taxes[0].rate, 18)

    def test_resolve_gst_leaves_the_order_alone_when_nothing_resolves(self):
        """No GSTIN on this demo Company (or a non-Indian customer) is a
        legitimate case - _resolve_gst must not invent a template."""
        doc = frappe.new_doc("Sales Order")
        doc.company = frappe.defaults.get_global_default("company")
        with patch(
            "india_compliance.gst_india.overrides.transaction.get_gst_details",
            return_value={},
        ):
            _resolve_gst(doc)
        self.assertFalse(doc.get("taxes_and_charges"))
        self.assertEqual(len(doc.get("taxes") or []), 0)

    # ------------------------------------------------------- mine / team's
    #
    # ORDER_CONFIG.owner_field used to be None, so the app's usual "My X /
    # My team's" toggle (Field Visit, Journey Plan, ...) had no way to work
    # for Sales Order - is_self was silently ignored. created_by_emp already
    # exists and is already reliably stamped by create_order (see
    # test_create_forces_the_signed_in_users_own_employee above); this just
    # wires the list config to use it.

    def test_order_list_is_self_filters_to_the_callers_own_orders(self):
        mine = create_order(**self._payload())
        other_employee = frappe.db.get_value(
            "Employee", {"user_id": "priya.tsm@demo.local", "status": "Active"}, "name"
        )
        theirs = create_order(**self._payload())
        if other_employee:
            frappe.db.set_value("Sales Order", theirs["name"], "created_by_emp", other_employee)

        frappe.form_dict.is_self = 1
        try:
            result = order_list()
        finally:
            frappe.form_dict.pop("is_self", None)
        names = {r["name"] for r in result["records"]}
        self.assertIn(mine["name"], names)
        self.assertNotIn(theirs["name"], names)

    def test_order_list_is_self_zero_excludes_the_callers_own_orders(self):
        mine = create_order(**self._payload())
        other_employee = frappe.db.get_value(
            "Employee", {"user_id": "priya.tsm@demo.local", "status": "Active"}, "name"
        )
        theirs = create_order(**self._payload())
        if other_employee:
            frappe.db.set_value("Sales Order", theirs["name"], "created_by_emp", other_employee)

        frappe.form_dict.is_self = 0
        try:
            result = order_list()
        finally:
            frappe.form_dict.pop("is_self", None)
        names = {r["name"] for r in result["records"]}
        self.assertNotIn(mine["name"], names)
        if other_employee:
            self.assertIn(theirs["name"], names)
