# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Tests for field sales pricing.

Each test here corresponds to a defect reproduced in the engine this replaces:
a rate guessed from a customer group's name, a warehouse lookup that could
never match a leaf, a missing price returned as a silent zero, and a Sales
Order that stored whatever rate the client sent.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from field_sales import pricing

PRICE_LIST = "Standard Selling"
LIST_RATE = 500.0


def ensure(doctype: str, name: str, values: dict) -> str:
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.new_doc(doctype)
    doc.update(values)
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


class TestPricing(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = frappe.get_all("Company", pluck="name")[0]
        cls.abbr = frappe.db.get_value("Company", cls.company, "abbr")

        # a warehouse tree with a real intermediate group
        cls.root_wh = f"All Warehouses - {cls.abbr}"
        cls.group_wh = ensure(
            "Warehouse", f"FS Test Region - {cls.abbr}",
            {"warehouse_name": "FS Test Region", "is_group": 1,
             "parent_warehouse": cls.root_wh, "company": cls.company},
        )
        cls.leaf_wh = ensure(
            "Warehouse", f"FS Test Depot - {cls.abbr}",
            {"warehouse_name": "FS Test Depot", "is_group": 0,
             "parent_warehouse": cls.group_wh, "company": cls.company},
        )

        cls.item = "FS-TEST-ITEM-001"
        if not frappe.db.exists("Item", cls.item):
            hsn = frappe.get_all("GST HSN Code", limit=1, pluck="name")
            cat = frappe.get_all("Item Category", limit=1, pluck="name")
            doc = frappe.new_doc("Item")
            doc.update({
                "item_code": cls.item, "item_name": "FS Test Item",
                "item_group": "All Item Groups", "stock_uom": "Kg",
                "is_stock_item": 0, "is_sales_item": 1,
            })
            if hsn:
                doc.gst_hsn_code = hsn[0]
            if cat:
                doc.item_category = cat[0]
            doc.flags.ignore_mandatory = True
            doc.insert(ignore_permissions=True)

        cls.customer = "FS Test Pricing Customer"
        if not frappe.db.exists("Customer", {"customer_name": cls.customer}):
            doc = frappe.new_doc("Customer")
            doc.update({
                "customer_name": cls.customer, "customer_type": "Company",
                "customer_group": "Commercial", "territory": "India",
                "business_type": "Registered", "gst_category": "Registered Regular",
            })
            doc.flags.ignore_mandatory = True
            doc.insert(ignore_permissions=True)
        cls.customer = frappe.db.get_value("Customer", {"customer_name": cls.customer}, "name")
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")
        self._clear_prices()
        self._clear_rules()
        frappe.db.set_value("Customer", self.customer, pricing.CUSTOMER_TYPE_FIELD, "")

    def tearDown(self):
        self._clear_prices()
        self._clear_rules()
        frappe.db.rollback()

    def _clear_prices(self):
        for name in frappe.get_all("Item Price", {"item_code": self.item}, pluck="name"):
            frappe.delete_doc("Item Price", name, force=True, ignore_permissions=True)

    def _clear_rules(self):
        for name in frappe.get_all("Pricing Rule", {"title": ["like", "FS Test%"]}, pluck="name"):
            frappe.delete_doc("Pricing Rule", name, force=True, ignore_permissions=True)

    def _price(self, rate=LIST_RATE, customer_type=None, warehouse=None, **extra):
        doc = frappe.new_doc("Item Price")
        doc.update({
            "item_code": self.item, "price_list": PRICE_LIST,
            "price_list_rate": rate, "uom": "Kg", "currency": "INR",
        })
        if customer_type:
            doc.customer_type = customer_type
        if warehouse:
            doc.warehouse = warehouse
        doc.update(extra)
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return doc.name

    # ------------------------------------------------------- customer type

    def test_customer_type_is_read_from_the_field(self):
        frappe.db.set_value("Customer", self.customer, pricing.CUSTOMER_TYPE_FIELD, "DL")
        self.assertEqual(pricing.resolve_customer_type(self.customer), "DL")

    def test_customer_group_name_does_not_decide_the_price_book(self):
        """"Midlands Trade" used to resolve to DL because of the letters in it."""
        group = "FS Test Midlands Trade"
        ensure("Customer Group", group, {
            "customer_group_name": group,
            "parent_customer_group": "All Customer Groups", "is_group": 0,
        })
        frappe.db.set_value("Customer", self.customer, "customer_group", group)
        frappe.db.set_value("Customer", self.customer, pricing.CUSTOMER_TYPE_FIELD, "")
        try:
            self.assertIsNone(pricing.resolve_customer_type(self.customer))
        finally:
            frappe.db.set_value("Customer", self.customer, "customer_group", "Commercial")

    def test_explicit_type_wins(self):
        self.assertEqual(pricing.resolve_customer_type(self.customer, "DP"), "DP")

    def test_nonsense_type_is_ignored(self):
        self.assertIsNone(pricing.resolve_customer_type(self.customer, "banana"))

    # ------------------------------------------------------- warehouse

    def test_warehouse_chain_is_specific_first(self):
        chain = pricing.warehouse_chain(self.leaf_wh)
        self.assertEqual(chain[0], self.leaf_wh)
        self.assertIn(self.group_wh, chain)
        self.assertIn(self.root_wh, chain)
        self.assertLess(chain.index(self.group_wh), chain.index(self.root_wh))

    def test_price_list_is_chosen_by_customer_type(self):
        """Customer type selects the price list, not individual rows.

        `Item Price.customer_type` is a fetch_from of `price_list.customer_type`,
        so dealer pricing means a dealer price list. The old engine filtered
        rows by type instead, and a dealer found nothing.
        """
        dl_list = ensure("Price List", "FS Test DL List", {
            "price_list_name": "FS Test DL List", "selling": 1, "enabled": 1,
            "currency": "INR", "customer_type": "DL",
        })
        frappe.db.set_value("Price List", dl_list, "customer_type", "DL")
        self.assertEqual(pricing.resolve_price_list(customer_type="DL"), dl_list)

    def test_explicit_price_list_wins(self):
        self.assertEqual(
            pricing.resolve_price_list(customer_type="DL", explicit=PRICE_LIST), PRICE_LIST
        )

    def test_price_on_a_leaf_warehouse_is_found(self):
        """The old engine jumped to the nearest group, so this returned 0."""
        self._price(rate=444.0, warehouse=self.leaf_wh)
        result = pricing.get_base_rate(self.item, PRICE_LIST, warehouse=self.leaf_wh)
        self.assertEqual(result["rate"], 444.0)

    def test_leaf_price_beats_an_ancestor_price(self):
        self._price(rate=LIST_RATE)
        self._price(rate=400.0, warehouse=self.group_wh)
        self._price(rate=350.0, warehouse=self.leaf_wh)
        self.assertEqual(
            pricing.get_base_rate(self.item, PRICE_LIST, warehouse=self.leaf_wh)["rate"], 350.0
        )

    def test_falls_back_up_the_tree(self):
        self._price(rate=400.0, warehouse=self.group_wh)
        self.assertEqual(
            pricing.get_base_rate(self.item, PRICE_LIST, warehouse=self.leaf_wh)["rate"], 400.0
        )

    def test_falls_back_to_the_plain_price_list(self):
        self._price(rate=LIST_RATE)
        self.assertEqual(
            pricing.get_base_rate(self.item, PRICE_LIST, warehouse=self.leaf_wh)["rate"], LIST_RATE
        )

    def test_warehouse_price_is_reachable_without_warehouse_context(self):
        """Prices are often stored against one stocking point. A caller with no
        warehouse must still get a number, flagged as a loose match."""
        self._price(rate=333.0, warehouse=self.leaf_wh)
        result = pricing.get_base_rate(self.item, PRICE_LIST)
        self.assertEqual(result["rate"], 333.0)
        self.assertEqual(result["matched_on"], "any warehouse")

    def test_an_exact_warehouse_match_is_preferred_over_the_loose_one(self):
        self._price(rate=333.0, warehouse=self.leaf_wh)
        self._price(rate=222.0, warehouse=self.group_wh)
        result = pricing.get_base_rate(self.item, PRICE_LIST, warehouse=self.leaf_wh)
        self.assertEqual(result["rate"], 333.0)
        self.assertIn(self.leaf_wh, result["matched_on"])

    # ------------------------------------------------------- missing price

    def test_a_missing_price_raises_instead_of_returning_zero(self):
        """The old engine returned 0 with status true."""
        with self.assertRaises(frappe.ValidationError):
            pricing.get_base_rate(self.item, PRICE_LIST, warehouse=self.leaf_wh)

    def test_an_expired_price_is_not_used(self):
        self._price(
            rate=LIST_RATE,
            valid_from=add_days(nowdate(), -30),
            valid_upto=add_days(nowdate(), -1),
        )
        with self.assertRaises(frappe.ValidationError):
            pricing.get_base_rate(self.item, PRICE_LIST)

    # ------------------------------------------------------- rules

    def _rule(self, title, **extra):
        doc = frappe.new_doc("Pricing Rule")
        doc.update({
            "title": title, "apply_on": "Item Code", "selling": 1,
            "price_or_product_discount": "Price",
            "rate_or_discount": "Discount Percentage", "discount_percentage": 10,
        })
        doc.update(extra)
        doc.append("items", {"item_code": self.item})
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return doc.name

    def test_a_neutral_rule_always_applies(self):
        self._price()
        self._rule("FS Test Neutral")
        result = pricing.calculate_rate(self.item, customer=self.customer, qty=1, price_list=PRICE_LIST)
        self.assertEqual(result["final_rate"], 450.0)

    def test_a_delivery_term_rule_only_applies_to_that_term(self):
        term = ensure("Delivery Term", "FS Test Door", {"delivery_term": "FS Test Door"})
        other = ensure("Delivery Term", "FS Test Ex Works", {"delivery_term": "FS Test Ex Works"})
        self._price()
        self._rule("FS Test Door Rule", custom_delivery_term=term)

        with_term = pricing.calculate_rate(
            self.item, customer=self.customer, delivery_term=term, price_list=PRICE_LIST
        )
        without = pricing.calculate_rate(
            self.item, customer=self.customer, delivery_term=other, price_list=PRICE_LIST
        )
        self.assertEqual(with_term["final_rate"], 450.0)
        self.assertEqual(without["final_rate"], LIST_RATE)

    def test_rule_title_is_not_parsed_for_meaning(self):
        """The old engine read tokens like -DLD and -75D out of the title."""
        self._price()
        self._rule("FS Test SOMETHING-DLD-75D-ADV")
        result = pricing.calculate_rate(self.item, customer=self.customer, delivery_term=None, price_list=PRICE_LIST)
        # applies because it names no term, not because of anything in its name
        self.assertEqual(result["final_rate"], 450.0)
        self.assertEqual(len(result["pricing_rules_applied"]), 1)

    def test_qty_band_is_respected(self):
        self._price()
        self._rule("FS Test Bulk", min_qty=100)
        self.assertEqual(pricing.calculate_rate(self.item, customer=self.customer, qty=10, price_list=PRICE_LIST)["final_rate"], LIST_RATE)
        self.assertEqual(pricing.calculate_rate(self.item, customer=self.customer, qty=150, price_list=PRICE_LIST)["final_rate"], 450.0)

    def test_rate_never_goes_below_zero(self):
        self._price(rate=10.0)
        self._rule("FS Test Huge", rate_or_discount="Discount Amount", discount_amount=999)
        self.assertEqual(pricing.calculate_rate(self.item, customer=self.customer, price_list=PRICE_LIST)["final_rate"], 0.0)

    # ------------------------------------------------------- enforcement

    def _sales_order(self, rate, **item_overrides):
        so = frappe.new_doc("Sales Order")
        so.update({
            "customer": self.customer, "company": self.company,
            "transaction_date": nowdate(),
            "delivery_date": add_days(nowdate(), 7),
            "currency": "INR", "selling_price_list": PRICE_LIST,
        })
        row = {
            "item_code": self.item, "qty": 10, "rate": rate,
            "delivery_date": add_days(nowdate(), 7),
        }
        row.update(item_overrides)
        so.append("items", row)
        so.flags.ignore_mandatory = True
        return so

    def test_a_client_supplied_rate_is_overridden(self):
        """The headline defect: an order could be booked at any price."""
        self._price()
        so = self._sales_order(rate=1)
        pricing.enforce_sales_order_rates(so)
        self.assertEqual(flt_(so.items[0].rate), LIST_RATE)

    def test_enforcement_applies_rules_too(self):
        self._price()
        self._rule("FS Test Neutral")
        so = self._sales_order(rate=1)
        pricing.enforce_sales_order_rates(so)
        self.assertEqual(flt_(so.items[0].rate), 450.0)

    def test_enforcement_populates_the_native_pricing_rules_field(self):
        """Sales Order Item.pricing_rules is core ERPNext's own field (used
        by the desk item grid's "view applied pricing rules" icon and by
        anything else reading the standard field rather than our own
        custom_pricing_rules_applied) - it has to carry the same shape
        ERPNext's own pricing_rule.py writes: a JSON array of rule names.

        Set on before_save, not before_validate, alongside
        enforce_sales_order_rates - see restore_native_pricing_rules_field's
        own docstring for why: ERPNext's own validate() unconditionally
        blanks pricing_rules back out whenever ignore_pricing_rule is set,
        so anything written before validate() runs never survives it."""
        self._price()
        self._rule("FS Test Neutral")
        so = self._sales_order(rate=1)
        pricing.enforce_sales_order_rates(so)
        pricing.restore_native_pricing_rules_field(so)
        self.assertEqual(json.loads(so.items[0].pricing_rules), ["FS Test Neutral"])

    def test_no_matching_rule_leaves_the_native_field_empty(self):
        self._price()
        so = self._sales_order(rate=1)
        pricing.enforce_sales_order_rates(so)
        pricing.restore_native_pricing_rules_field(so)
        self.assertEqual(so.items[0].pricing_rules, "")

    def test_the_native_field_survives_a_real_insert(self):
        """The two unit tests above call enforce_sales_order_rates and
        restore_native_pricing_rules_field directly, in the right order -
        this one goes through frappe's actual save lifecycle (both hooks
        fire the way hooks.py wires them, via before_validate then
        before_save) to prove the field really does survive ERPNext's own
        validate(), not just this file's own call order."""
        self._price()
        self._rule("FS Test Neutral")
        so = self._sales_order(rate=1)
        so.insert(ignore_permissions=True)
        try:
            self.assertEqual(json.loads(so.items[0].pricing_rules), ["FS Test Neutral"])
            stored = frappe.db.get_value("Sales Order Item", so.items[0].name, "pricing_rules")
            self.assertEqual(json.loads(stored), ["FS Test Neutral"])
        finally:
            frappe.delete_doc("Sales Order", so.name, force=True, ignore_permissions=True)

    def test_enforcement_refuses_to_price_at_zero(self):
        """rate=0 (unset) means the rep didn't enter one - unlike a nonzero
        manual rate (see the manual-rate tests below), that's still refused
        rather than silently booked at zero."""
        so = self._sales_order(rate=0)
        with self.assertRaises(frappe.ValidationError):
            pricing.enforce_sales_order_rates(so)

    # ------------------------------------------------------- manual rate
    #
    # No custom field for this - Sales Order Item.rate is the standard field
    # ERPNext already ships. A client-sent rate is normally worthless (every
    # other test above proves it gets overwritten) - it only ever survives
    # once calculate_rate has already raised PriceNotFound for that item, at
    # which point there's genuinely nothing else to book against.

    def test_a_manual_rate_is_ignored_when_a_real_price_exists(self):
        """The headline defect this whole function exists to prevent, still
        holding for the one row where a client-sent rate is ever read at
        all: it can't be used to undercut a price that does exist."""
        self._price()
        so = self._sales_order(rate=1)
        pricing.enforce_sales_order_rates(so)
        self.assertEqual(flt_(so.items[0].rate), LIST_RATE)

    def test_a_manual_rate_fills_a_genuine_price_gap(self):
        so = self._sales_order(rate=99)
        pricing.enforce_sales_order_rates(so)
        self.assertEqual(flt_(so.items[0].rate), 99.0)

    # ------------------------------------------------------- rule caching
    #
    # Production has ~1,200 active selling Pricing Rules. find_pricing_rules
    # used to re-fetch all of them, plus one extra query per rule to check
    # its item-code restriction, on every single call - so pricing a
    # multi-item order meant thousands of queries. _active_selling_rules
    # caches that per request; these tests exist because a cache is only
    # safe if it's invalidated the moment the thing it cached changes.

    def test_a_new_rule_is_seen_without_restarting_the_request(self):
        """Covered implicitly by every other rule test in this file
        (each creates its rule then immediately prices against it) - this
        one names the actual behaviour being relied on: inserting a Pricing
        Rule must invalidate the cache, not just updating an existing one."""
        self._price()
        pricing.calculate_rate(self.item, customer=self.customer, price_list=PRICE_LIST)
        self._rule("FS Test Freshly Created")
        result = pricing.calculate_rate(self.item, customer=self.customer, price_list=PRICE_LIST)
        self.assertEqual(result["final_rate"], 450.0)

    def test_a_disabled_rule_stops_applying_immediately(self):
        self._price()
        name = self._rule("FS Test Then Disabled")
        pricing.calculate_rate(self.item, customer=self.customer, price_list=PRICE_LIST)  # warms the cache

        frappe.db.set_value("Pricing Rule", name, "disable", 1)
        frappe.get_doc("Pricing Rule", name).run_method("on_update")  # what the real save() does

        result = pricing.calculate_rate(self.item, customer=self.customer, price_list=PRICE_LIST)
        self.assertEqual(result["final_rate"], LIST_RATE)

    def test_item_restrictions_do_not_leak_between_rules(self):
        """The batched Pricing Rule Item Code lookup groups rows by their
        own parent - a rule restricted to a different item must not leak
        onto this one just because both were fetched in the same query."""
        hsn = frappe.get_all("GST HSN Code", limit=1, pluck="name")
        cat = frappe.get_all("Item Category", limit=1, pluck="name")
        other_item = ensure("Item", "FS-TEST-ITEM-002", {
            "item_code": "FS-TEST-ITEM-002", "item_name": "FS Test Item Two",
            "item_group": "All Item Groups", "stock_uom": "Kg",
            "is_stock_item": 0, "is_sales_item": 1,
            "gst_hsn_code": hsn[0] if hsn else None,
            "item_category": cat[0] if cat else None,
        })
        self._price()
        rule = frappe.get_doc("Pricing Rule", self._rule("FS Test Only Item Two"))
        rule.items = []
        rule.append("items", {"item_code": other_item})
        rule.flags.ignore_mandatory = True
        rule.save(ignore_permissions=True)

        result = pricing.calculate_rate(self.item, customer=self.customer, price_list=PRICE_LIST)
        self.assertEqual(result["final_rate"], LIST_RATE, "a rule scoped to a different item must not apply here")

    def test_enforcement_stops_erpnext_recomputing(self):
        self._price()
        so = self._sales_order(rate=1)
        pricing.enforce_sales_order_rates(so)
        self.assertEqual(so.ignore_pricing_rule, 1)


def flt_(v):
    from frappe.utils import flt

    return flt(v, 2)
