# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the modules that run on native doctypes: customers, complaints,
the catalogue and orders."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from field_sales.api import catalog, complaints, customers
from field_sales.api.listing import paginated_list

TERRITORY = "Kolkata Area"
OTHER_TERRITORY = "Pune Area"
REP = "ravi.tsm@demo.local"


class TestNativeModules(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = frappe.db.get_value(
            "Customer", {"territory": TERRITORY}, "name"
        ) or frappe.db.get_value("Customer", {}, "name")
        cls.employee = frappe.db.get_value("Employee", {"user_id": REP}, "name")
        # an item that actually carries a price, not just any sellable item
        cls.item = frappe.db.get_value(
            "Item Price", {"price_list": "Standard Selling", "selling": 1}, "item_code"
        )
        cls.company = frappe.get_all("Company", pluck="name")[0]

        # `mohan_impex` marks these custom fields mandatory on core doctypes -
        # one of the portability defects in the audit. They do not exist on a
        # clean field_sales install, so the tests satisfy them only if present.
        cls.legacy_issue = {}
        if frappe.get_meta("Issue").get_field("claim_type") and \
                frappe.get_meta("Issue").get_field("claim_type").reqd:
            cls.legacy_issue["claim_type"] = "Transit"
        cls.legacy_so = {}
        so_shop = frappe.get_meta("Sales Order").get_field("shop")
        if so_shop and so_shop.reqd:
            cls.legacy_so["shop"] = frappe.db.get_value("Shop", {}, "name")
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._cleanup()

    def tearDown(self):
        frappe.set_user("Administrator")
        self._cleanup()
        frappe.db.rollback()

    def _cleanup(self):
        for name in frappe.get_all("Issue", {"subject": ["like", "FS Test%"]}, pluck="name"):
            frappe.delete_doc("Issue", name, force=True, ignore_permissions=True)
        for name in frappe.get_all("Customer Change Request", pluck="name"):
            frappe.delete_doc("Customer Change Request", name, force=True,
                              ignore_permissions=True)

    # ------------------------------------------------------------ customers

    def test_customer_list_returns_customers(self):
        result = paginated_list(customers.CUSTOMER_CONFIG, form={}, user="Administrator")
        self.assertGreater(result["total_count"], 0)

    def test_customer_list_is_territory_scoped(self):
        result = paginated_list(customers.CUSTOMER_CONFIG, form={}, user=REP)
        territories = {r["territory"] for r in result["records"]}
        self.assertTrue(
            territories <= {TERRITORY},
            f"a rep saw customers outside their territory: {territories}",
        )

    def test_customer_list_search_is_parameterised(self):
        result = paginated_list(
            customers.CUSTOMER_CONFIG,
            form={"search_text": '" or 1=1 or customer_name LIKE "'},
            user="Administrator",
        )
        self.assertEqual(result["total_count"], 0)

    def test_customer_detail_includes_addresses_and_contacts(self):
        data = customers.customer(self.customer)
        self.assertIn("addresses", data)
        self.assertIn("contacts", data)
        self.assertIsInstance(data["addresses"], list)

    def test_customer_list_offers_no_mine_toggle(self):
        """Customer has no 'raised by', so the toggle is absent rather than faked."""
        self.assertIsNone(customers.CUSTOMER_CONFIG.owner_field)

    def test_ledger_totals(self):
        ledger = customers.customer_ledger(self.customer)
        self.assertIn("total_outstanding", ledger)
        self.assertIn("invoices", ledger)
        self.assertGreaterEqual(ledger["total_billed"], 0)

    def test_ledger_date_range_is_not_string_formatted(self):
        """The original pasted from_date/to_date straight into SQL."""
        ledger = customers.customer_ledger(
            self.customer,
            from_date=add_days(nowdate(), -365),
            to_date=nowdate(),
        )
        self.assertIsInstance(ledger["invoices"], list)

    def test_ledger_rejects_a_bad_date(self):
        with self.assertRaises(Exception):
            customers.customer_ledger(
                self.customer, from_date="'; drop table `tabUser`; --", to_date=nowdate()
            )
        self.assertTrue(frappe.db.exists("DocType", "User"))

    def test_change_request_is_created_instead_of_editing(self):
        frappe.set_user(REP)
        try:
            result = customers.request_customer_change(
                self.customer, "Phone number is wrong, should be 98300 12345"
            )
        finally:
            frappe.set_user("Administrator")
        doc = frappe.get_doc("Customer Change Request", result["name"])
        self.assertEqual(doc.status, "Pending")
        self.assertEqual(doc.customer, self.customer)

    def test_empty_change_request_is_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            customers.request_customer_change(self.customer, "   ")

    def test_my_territories_reports_the_scope(self):
        frappe.set_user(REP)
        try:
            result = customers.my_territories()
        finally:
            frappe.set_user("Administrator")
        self.assertIn(TERRITORY, result["territories"])
        self.assertFalse(result["unrestricted"])

    # ------------------------------------------------------------ complaints

    def _complaint(self, **overrides):
        payload = {
            "subject": "FS Test bags torn in transit",
            "description": "Three bags arrived split.",
            "customer": self.customer,
            "fs_claim_type": "Transit",
        }
        if self.legacy_issue:
            # `mohan_impex` makes Issue.claim_type mandatory. The product
            # endpoint deliberately does not know about another app's fields,
            # so it cannot populate it. On a clean field_sales install the
            # field does not exist and these tests run.
            self.skipTest(
                "Issue has legacy mandatory field(s) %s from another installed app"
                % ", ".join(self.legacy_issue)
            )
        payload.update(overrides)
        return complaints.raise_complaint(**payload)

    def test_raising_a_complaint(self):
        frappe.set_user(REP)
        try:
            result = self._complaint()
        finally:
            frappe.set_user("Administrator")
        doc = frappe.get_doc("Issue", result["name"])
        self.assertEqual(doc.fs_claim_type, "Transit")
        self.assertEqual(doc.fs_sales_person, self.employee)
        self.assertTrue(doc.fs_territory, "territory was not derived")

    def test_complaint_requires_a_subject(self):
        with self.assertRaises(frappe.ValidationError):
            self._complaint(subject="   ")

    def test_complaint_ignores_fields_the_client_may_not_set(self):
        frappe.set_user(REP)
        try:
            result = self._complaint(fs_sales_person="Nonexistent", status="Closed")
        finally:
            frappe.set_user("Administrator")
        doc = frappe.get_doc("Issue", result["name"])
        self.assertEqual(doc.fs_sales_person, self.employee)
        self.assertNotEqual(doc.status, "Closed")

    def test_complaint_list_tabs(self):
        frappe.set_user(REP)
        try:
            opened = self._complaint()
        finally:
            frappe.set_user("Administrator")
        open_rows = paginated_list(
            complaints.COMPLAINT_CONFIG, form={"tab": "open"}, user="Administrator")
        self.assertIn(opened["name"], [r["name"] for r in open_rows["records"]])

    def test_resolving_a_complaint_stamps_the_date(self):
        frappe.set_user(REP)
        try:
            raised = self._complaint()
        finally:
            frappe.set_user("Administrator")
        result = complaints.resolve_complaint(raised["name"], resolution="Replaced")
        self.assertEqual(result["status"], "Resolved")
        self.assertEqual(str(result["resolved_on"]), nowdate())

    # ------------------------------------------------------------ catalogue

    def test_item_list_returns_items(self):
        result = paginated_list(catalog.ITEM_CONFIG, form={}, user="Administrator")
        self.assertGreater(result["total_count"], 0)

    def test_price_list_carries_a_rate(self):
        page = catalog.price_list(customer=self.customer, limit=5)
        self.assertTrue(page["records"])
        priced = [r for r in page["records"] if r.get("rate") is not None]
        self.assertTrue(priced, "no row came back with a rate")

    def test_an_unpriced_item_is_null_not_zero(self):
        """The old engine returned 0.00 for a missing price and let it through."""
        code = "FS-TEST-UNPRICED-001"
        if not frappe.db.exists("Item", code):
            hsn = frappe.get_all("GST HSN Code", limit=1, pluck="name")
            cat = frappe.get_all("Item Category", limit=1, pluck="name")
            doc = frappe.new_doc("Item")
            doc.update({"item_code": code, "item_name": "FS Test Unpriced",
                        "item_group": "All Item Groups", "stock_uom": "Kg",
                        "is_stock_item": 0, "is_sales_item": 1})
            if hsn:
                doc.gst_hsn_code = hsn[0]
            if cat:
                doc.item_category = cat[0]
            doc.flags.ignore_mandatory = True
            doc.insert(ignore_permissions=True)

        page = catalog.price_list(customer=self.customer, search_text="FS Test Unpriced")
        rows = [r for r in page["records"] if r["item_code"] == code]
        self.assertTrue(rows)
        self.assertIsNone(rows[0]["rate"], "an unpriced item came back as a number")

    def test_item_price_matches_what_an_order_would_store(self):
        """The quote a rep sees must equal the rate the server enforces."""
        quoted = catalog.item_price(item_code=self.item, customer=self.customer, qty=10)

        so = frappe.new_doc("Sales Order")
        so.update({
            "customer": self.customer, "company": self.company,
            "transaction_date": nowdate(),
            "delivery_date": add_days(nowdate(), 7),
            "currency": "INR",
        })
        so.update(self.legacy_so)
        so.append("items", {"item_code": self.item, "qty": 10, "rate": 1,
                            "delivery_date": add_days(nowdate(), 7)})
        so.flags.ignore_mandatory = True
        so.insert(ignore_permissions=True)

        self.assertEqual(float(so.items[0].rate), float(quoted["final_rate"]))

    def test_warehouses_are_listed(self):
        rows = catalog.warehouses()
        self.assertTrue(rows)
        self.assertNotIn(1, [r.get("is_group") for r in rows])

    # ------------------------------------------------------------ orders

    def test_order_list_is_territory_scoped(self):
        result = paginated_list(catalog.ORDER_CONFIG, form={}, user=REP)
        territories = {r["territory"] for r in result["records"] if r.get("territory")}
        self.assertTrue(
            territories <= {TERRITORY},
            f"a rep saw orders outside their territory: {territories}",
        )

    def test_order_list_injection(self):
        result = paginated_list(
            catalog.ORDER_CONFIG,
            form={"search_text": '" or 1=1 or name LIKE "'},
            user="Administrator",
        )
        self.assertEqual(result["total_count"], 0)
