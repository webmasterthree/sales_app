# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for the modules that run on native doctypes: customers, complaints,
the catalogue and orders."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, now_datetime, nowdate

from field_sales import pricing
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

        cls.field_reason = frappe.db.get_value(
            "Field Reason", {"applies_to": "Visit"}, "name"
        )
        if not cls.field_reason:
            reason_doc = frappe.new_doc("Field Reason")
            reason_doc.update({"reason": "FS Test Convert Reason", "applies_to": "Visit"})
            reason_doc.flags.ignore_mandatory = True
            reason_doc.insert(ignore_permissions=True)
            cls.field_reason = reason_doc.name

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
        for name in frappe.get_all(
            "Sales Order", {"remarks": ["like", "Converted from Field Visit%"]}, pluck="name"
        ):
            doc = frappe.get_doc("Sales Order", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Sales Order", name, force=True, ignore_permissions=True)
        for name in frappe.get_all("Field Visit", {"outlet_name": ["like", "FS Test%"]}, pluck="name"):
            doc = frappe.get_doc("Field Visit", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Field Visit", name, force=True, ignore_permissions=True)

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

    def test_change_requests_list_shows_what_was_raised(self):
        """The Change Log a rep checks before raising another request."""
        frappe.set_user(REP)
        try:
            customers.request_customer_change(self.customer, "Shop moved to a new address")
        finally:
            frappe.set_user("Administrator")
        log = customers.customer_change_requests(self.customer)
        self.assertTrue(any(r["requested_change"] == "Shop moved to a new address" for r in log))
        self.assertEqual(log[0]["status"], "Pending")

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

    def test_complaint_stores_reasons_and_claimed_items(self):
        """Reason-for-complaint (multi-select + remark) and the per-item
        claim table, ported from the Flutter form's AddComplaintScreen -
        see fs_complaint_reasons/fs_complaint_items on Issue."""
        frappe.set_user(REP)
        try:
            result = self._complaint(
                fs_complaint_reasons=[
                    {"reason": "Damaged in transit", "remarks": "Box was crushed"},
                    {"reason": "Product quality issue", "remarks": ""},
                ],
                fs_complaint_items=[
                    {
                        "item_code": self.item,
                        "qty": 5,
                        "value_of_goods": 250,
                        "batch_no": "B-100",
                        "mfd": "2026-01-01",
                        "expiry_date": "2027-01-01",
                    },
                ],
            )
        finally:
            frappe.set_user("Administrator")

        doc = frappe.get_doc("Issue", result["name"])
        self.assertEqual(len(doc.fs_complaint_reasons), 2)
        self.assertEqual(doc.fs_complaint_reasons[0].reason, "Damaged in transit")
        self.assertEqual(doc.fs_complaint_reasons[0].remarks, "Box was crushed")

        self.assertEqual(len(doc.fs_complaint_items), 1)
        row = doc.fs_complaint_items[0]
        self.assertEqual(row.item_code, self.item)
        self.assertEqual(row.qty, 5)
        self.assertEqual(row.batch_no, "B-100")

    def test_complaint_child_tables_ignore_unlisted_fields(self):
        """Only WRITABLE_TABLES-declared fields may land on the child rows."""
        frappe.set_user(REP)
        try:
            result = self._complaint(
                fs_complaint_items=[
                    {"item_code": self.item, "qty": 1, "idx": 999, "name": "hax"},
                ],
            )
        finally:
            frappe.set_user("Administrator")
        doc = frappe.get_doc("Issue", result["name"])
        self.assertEqual(len(doc.fs_complaint_items), 1)
        self.assertNotEqual(doc.fs_complaint_items[0].name, "hax")

    # ------------------------------------------------------------ catalogue

    def test_item_list_returns_items(self):
        result = paginated_list(catalog.ITEM_CONFIG, form={}, user="Administrator")
        self.assertGreater(result["total_count"], 0)

    def test_price_list_carries_a_rate(self):
        page = catalog.price_list(customer=self.customer, limit=5)
        self.assertTrue(page["records"])
        priced = [r for r in page["records"] if r.get("rate") is not None]
        self.assertTrue(priced, "no row came back with a rate")

    def test_price_list_row_shows_which_pricing_rule_applied(self):
        """The rate a rep sees has no explanation on its own - this is what
        Form.vue/Detail.vue read to show "Scheme applied: ..." rather than
        a bare, unexplained number."""
        rule = frappe.new_doc("Pricing Rule")
        rule.update({
            "title": "FS Test Native Scheme", "apply_on": "Item Code", "selling": 1,
            "price_or_product_discount": "Price",
            "rate_or_discount": "Discount Percentage", "discount_percentage": 10,
        })
        rule.append("items", {"item_code": self.item})
        rule.flags.ignore_mandatory = True
        rule.insert(ignore_permissions=True)
        try:
            page = catalog.price_list(customer=self.customer, search_text=self.item)
            row = next(r for r in page["records"] if r["item_code"] == self.item)
            self.assertTrue(row.get("pricing_rules_applied"))
            self.assertEqual(row["pricing_rules_applied"][0]["title"], "FS Test Native Scheme")
        finally:
            frappe.delete_doc("Pricing Rule", rule.name, force=True, ignore_permissions=True)

    def _template_with_variant(self):
        hsn = frappe.get_all("GST HSN Code", limit=1, pluck="name")
        cat = frappe.get_all("Item Category", limit=1, pluck="name")
        template_code = "FS-TEST-TEMPLATE-001"
        variant_code = "FS-TEST-TEMPLATE-001-V1"
        attribute = "FS Test Pack Size"
        if not frappe.db.exists("Item Attribute", attribute):
            attr = frappe.new_doc("Item Attribute")
            attr.attribute_name = attribute
            attr.append("item_attribute_values", {"attribute_value": "1kg", "abbr": "1KG"})
            attr.flags.ignore_mandatory = True
            attr.insert(ignore_permissions=True)
        if not frappe.db.exists("Item", template_code):
            doc = frappe.new_doc("Item")
            doc.update({
                "item_code": template_code, "item_name": "FS Test Template",
                "item_group": "All Item Groups", "stock_uom": "Kg",
                "is_stock_item": 0, "is_sales_item": 1, "has_variants": 1,
            })
            doc.append("attributes", {"attribute": attribute})
            if hsn:
                doc.gst_hsn_code = hsn[0]
            if cat:
                doc.item_category = cat[0]
            doc.flags.ignore_mandatory = True
            doc.insert(ignore_permissions=True)
        if not frappe.db.exists("Item", variant_code):
            doc = frappe.new_doc("Item")
            doc.update({
                "item_code": variant_code, "item_name": "FS Test Template Variant",
                "item_group": "All Item Groups", "stock_uom": "Kg",
                "is_stock_item": 0, "is_sales_item": 1, "variant_of": template_code,
            })
            doc.append("attributes", {"attribute": attribute, "attribute_value": "1kg"})
            if hsn:
                doc.gst_hsn_code = hsn[0]
            if cat:
                doc.item_category = cat[0]
            doc.flags.ignore_mandatory = True
            doc.insert(ignore_permissions=True)
        if not frappe.db.exists(
            "Item Price", {"item_code": variant_code, "price_list": "Standard Selling", "selling": 1}
        ):
            price = frappe.new_doc("Item Price")
            price.update({
                "item_code": variant_code, "price_list": "Standard Selling",
                "price_list_rate": 99, "uom": "Kg", "currency": "INR", "selling": 1,
            })
            price.flags.ignore_mandatory = True
            price.insert(ignore_permissions=True)
        return template_code, variant_code

    def test_item_templates_shows_the_template_not_its_variant(self):
        """The order form's first picker: a rep chooses a product family,
        then (if it has variants) drills into item_variants for the
        specific pack/size - it must never offer a bare variant directly."""
        template_code, variant_code = self._template_with_variant()
        records = catalog.item_templates(search_text="FS Test Template")
        codes = {r["item_code"] for r in records}
        self.assertIn(template_code, codes)
        self.assertNotIn(variant_code, codes)

    def test_price_list_shows_the_variant_not_its_template(self):
        """The opposite shape for a flat catalogue browse: the template
        itself can never carry a rate, only its variants can."""
        template_code, variant_code = self._template_with_variant()
        page = catalog.price_list(customer=self.customer, search_text="FS Test Template")
        codes = {r["item_code"] for r in page["records"]}
        self.assertIn(variant_code, codes)
        self.assertNotIn(template_code, codes)

    def _unpriced_item(self):
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
        return code

    def test_an_unpriced_item_is_excluded_from_the_price_list(self):
        """A rep browsing the Price List screen has no use for a row that
        will only ever read "Unpriced", and a real order can't be booked
        with it anyway (enforce_sales_order_rates raises PriceNotFound) - so
        it is left off the list entirely rather than shown as a dead end."""
        self._unpriced_item()
        page = catalog.price_list(customer=self.customer, search_text="FS Test Unpriced")
        self.assertFalse(page["records"], "an item with no price on this list should not appear at all")

    def test_an_unpriced_item_raises_rather_than_returning_zero(self):
        """The old engine returned 0.00 for a missing price and let it through."""
        code = self._unpriced_item()
        with self.assertRaises(pricing.PriceNotFound):
            catalog.item_price(item_code=code, customer=self.customer)

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
        """A rep picks the regional depot they work out of (Kolkata, Dankuni,
        ...), not one of its granular internal leaves (Cold Room, a specific
        transit godown, ...) - only non-root group warehouses should show."""
        rows = catalog.warehouses()
        self.assertTrue(rows)
        is_group = {r["name"]: frappe.db.get_value("Warehouse", r["name"], "is_group") for r in rows}
        self.assertNotIn(0, is_group.values())
        parents = {r["name"]: frappe.db.get_value("Warehouse", r["name"], "parent_warehouse") for r in rows}
        self.assertNotIn("", parents.values(), "the company's synthetic tree root must not be offered")

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

    # ------------------------------------------------------ convert visit

    def _priced_item(self, rate=250):
        """A sellable item with a real Standard Selling rate, created once
        and reused - independent of ``cls.item``, which resolves from
        whatever Item Price rows happen to exist on this bench and cannot be
        relied on to carry a price (see test_an_unpriced_item_is_null_not_zero
        for the same reason ``FS-TEST-UNPRICED-001`` is built by hand rather
        than picked from existing data)."""
        code = "FS-TEST-CONVERT-ITEM"
        if not frappe.db.exists("Item", code):
            doc = frappe.new_doc("Item")
            doc.update({
                "item_code": code, "item_name": "FS Test Convert Item",
                "item_group": "All Item Groups", "stock_uom": "Nos",
                "is_stock_item": 0, "is_sales_item": 1,
            })
            hsn = frappe.get_all("GST HSN Code", limit=1, pluck="name")
            cat = frappe.get_all("Item Category", limit=1, pluck="name")
            if hsn:
                doc.gst_hsn_code = hsn[0]
            if cat:
                doc.item_category = cat[0]
            doc.flags.ignore_mandatory = True
            doc.insert(ignore_permissions=True)
        if not frappe.db.exists(
            "Item Price", {"item_code": code, "price_list": "Standard Selling", "selling": 1}
        ):
            price = frappe.new_doc("Item Price")
            price.update({
                "item_code": code, "price_list": "Standard Selling",
                "selling": 1, "price_list_rate": rate,
            })
            price.insert(ignore_permissions=True)
        return code

    def _unpriced_item(self):
        code = "FS-TEST-CONVERT-UNPRICED"
        if not frappe.db.exists("Item", code):
            doc = frappe.new_doc("Item")
            doc.update({
                "item_code": code, "item_name": "FS Test Convert Unpriced Item",
                "item_group": "All Item Groups", "stock_uom": "Nos",
                "is_stock_item": 0, "is_sales_item": 1,
            })
            hsn = frappe.get_all("GST HSN Code", limit=1, pluck="name")
            cat = frappe.get_all("Item Category", limit=1, pluck="name")
            if hsn:
                doc.gst_hsn_code = hsn[0]
            if cat:
                doc.item_category = cat[0]
            doc.flags.ignore_mandatory = True
            doc.insert(ignore_permissions=True)
        return code

    def _visit(self, submit=True, pitched_items=None, **overrides):
        payload = dict(
            party_type="Customer",
            customer=self.customer,
            outlet_name="FS Test Convert Outlet",
            visit_date=nowdate(),
            order_status="With Order",
            sales_person=self.employee,
            check_in=now_datetime(),
            check_out=now_datetime(),
        )
        payload.update(overrides)
        doc = frappe.new_doc("Field Visit")
        doc.update(payload)
        if pitched_items is None:
            pitched_items = [{"item_code": self._priced_item(), "qty": 5, "uom": "Nos"}]
        for row in pitched_items:
            doc.append("pitched_items", row)
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        if submit:
            doc.submit()
        return doc

    def _convert(self, visit_name):
        frappe.set_user(REP)
        try:
            return catalog.convert_visit_to_order(visit_name)
        finally:
            frappe.set_user("Administrator")

    def test_convert_creates_a_linked_draft_order(self):
        visit = self._visit()
        result = self._convert(visit.name)
        order = frappe.get_doc("Sales Order", result["name"])
        self.assertEqual(order.docstatus, 0)
        self.assertEqual(order.fs_field_visit, visit.name)
        self.assertEqual(order.customer, visit.customer)
        self.assertEqual(len(order.items), 1)
        self.assertEqual(order.items[0].qty, 5)

    def test_convert_only_copies_priced_pitched_items(self):
        """A pitched item with no resolvable price is left off the order,
        not invented a price or left to crash the whole conversion - see
        catalog.convert_visit_to_order's docstring."""
        priced = self._priced_item()
        unpriced = self._unpriced_item()
        visit = self._visit(pitched_items=[
            {"item_code": priced, "qty": 12, "uom": "Nos"},
            {"item_code": unpriced, "qty": 3, "uom": "Nos"},
        ])
        result = self._convert(visit.name)
        order = frappe.get_doc("Sales Order", result["name"])
        self.assertEqual([r.item_code for r in order.items], [priced])
        self.assertEqual(order.items[0].qty, 12)
        self.assertIn(unpriced, order.remarks)

    def test_convert_refuses_a_visit_with_no_priced_pitch(self):
        visit = self._visit(pitched_items=[])
        with self.assertRaises(frappe.ValidationError):
            self._convert(visit.name)

    def test_convert_refuses_a_draft_visit(self):
        visit = self._visit(submit=False)
        with self.assertRaises(frappe.ValidationError):
            self._convert(visit.name)

    def test_convert_refuses_a_prospect_visit(self):
        visit = self._visit(
            party_type="Prospect", customer=None, prospect_name="FS Test Prospect"
        )
        with self.assertRaises(frappe.ValidationError):
            self._convert(visit.name)

    def test_convert_refuses_a_visit_marked_without_order(self):
        visit = self._visit(order_status="Without Order", reason=self.field_reason)
        with self.assertRaises(frappe.ValidationError):
            self._convert(visit.name)

    def test_convert_refuses_a_visit_already_converted(self):
        visit = self._visit()
        first = self._convert(visit.name)
        self.assertTrue(first["name"])
        with self.assertRaises(frappe.ValidationError):
            self._convert(visit.name)

    # ------------------------------------------------------ warehouse scope

    def test_warehouses_are_company_scoped_for_a_rep(self):
        """Spec: "Warehouse list should show only allowed warehouses." Native
        Warehouse has no territory field (see catalog.warehouses'
        docstring), so this checks the company boundary that stands in for
        it - a rep never sees a warehouse outside their own Employee.company."""
        frappe.set_user(REP)
        try:
            rows = catalog.warehouses()
        finally:
            frappe.set_user("Administrator")
        rep_company = frappe.db.get_value("Employee", self.employee, "company")
        seen_companies = {
            frappe.db.get_value("Warehouse", r["name"], "company") for r in rows
        }
        self.assertTrue(
            seen_companies <= {rep_company},
            f"a rep saw warehouses outside their own company: {seen_companies}",
        )

    def test_warehouses_are_unrestricted_for_administrator(self):
        all_group_warehouses = {
            w.name for w in frappe.get_all(
                "Warehouse", {"disabled": 0, "is_group": 1, "parent_warehouse": ["is", "set"]}
            )
        }
        rows = {r["name"] for r in catalog.warehouses()}
        self.assertEqual(rows, all_group_warehouses)
