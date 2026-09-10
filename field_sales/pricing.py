# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Rate calculation for field sales.

Replaces `mohan_impex.pricing_engine`. The pricing *model* is kept - a rate is
derived from customer type, warehouse, delivery term, payment term and
quantity band, which is more than ERPNext models on its own. The machinery is
not:

* customer type is read from a field, never guessed from a name,
* warehouses are matched most-specific-first, then up the tree, rather than
  jumping straight to the nearest group,
* Pricing Rules are matched on explicit link fields, never by parsing their
  titles for tokens like ``-DLD`` or ``-75D``,
* a price that cannot be resolved is an error the caller must handle, never a
  silent zero,
* and the computed rate is enforced on the server, so a client cannot name its
  own price.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

CUSTOMER_TYPE_FIELD = "custom_customer_type_pricing"
VALID_CUSTOMER_TYPES = ("DL", "DP")


class PriceNotFound(frappe.ValidationError):
    """No price could be resolved. Never silently treated as zero."""


# ---------------------------------------------------------------- context


def resolve_customer_type(customer: str | None, explicit: str | None = None) -> str | None:
    """Dealer or distributor, read from the field that holds it.

    The implementation this replaces searched the *customer group name* for the
    letters "DL" or "DP", so a group called "Midlands Trade" resolved to DL. It
    then fell back to `Customer.customer_type`, whose options are
    Company / Individual / Partnership, and so could never match.
    """
    if explicit in VALID_CUSTOMER_TYPES:
        return explicit
    if not customer:
        return None

    value = frappe.db.get_value("Customer", customer, CUSTOMER_TYPE_FIELD)
    return value if value in VALID_CUSTOMER_TYPES else None


def warehouse_chain(warehouse: str | None) -> list[str]:
    """The warehouse itself, then each ancestor, most specific first.

    Prices are usually keyed to the warehouse a rep actually picks, which is a
    leaf. Resolving straight to the nearest group - as the old engine did -
    means those rows never match, because in a default ERPNext tree the nearest
    group is the root.
    """
    if not warehouse:
        return []

    chain, seen, current = [], set(), warehouse
    while current and current not in seen:
        seen.add(current)
        chain.append(current)
        current = frappe.db.get_value("Warehouse", current, "parent_warehouse")
    return chain


# ---------------------------------------------------------------- base rate


def resolve_price_list(
    customer: str | None = None,
    customer_type: str | None = None,
    explicit: str | None = None,
) -> str:
    """Pick the price list to read rates from.

    Customer type is a property of the *price list*, not of individual rows:
    `Item Price.customer_type` is a fetch_from of `price_list.customer_type`.
    So dealer versus distributor pricing means choosing a different price list,
    not filtering rows - which is what the engine this replaces tried to do,
    and why a dealer could find no price at all.
    """
    if explicit:
        return explicit

    if customer:
        own = frappe.db.get_value("Customer", customer, "default_price_list")
        if own:
            return own

    if customer_type:
        match = frappe.get_all(
            "Price List",
            filters={"selling": 1, "enabled": 1, "customer_type": customer_type},
            pluck="name",
            order_by="modified desc",
            ignore_permissions=True,
        )
        if match:
            return match[0]

    return (
        frappe.db.get_single_value("Selling Settings", "selling_price_list")
        or "Standard Selling"
    )


def get_base_rate(
    item_code: str,
    price_list: str,
    warehouse: str | None = None,
    transaction_date: str | None = None,
) -> dict:
    """Resolve the list price, most specific warehouse first.

    Returns ``{"rate": float, "matched_on": str, "item_price": str}``.
    Raises PriceNotFound when nothing matches - a missing price is a condition
    the rep has to see, not a zero that quietly flows into an order.
    """
    if not item_code:
        frappe.throw(_("Item is required to resolve a price."), PriceNotFound)
    if not price_list:
        frappe.throw(_("A price list is required to resolve a price."), PriceNotFound)

    txn_date = transaction_date or nowdate()

    candidates: list[tuple[str, dict]] = [
        (f"warehouse ({wh})", {"warehouse": wh}) for wh in warehouse_chain(warehouse)
    ]
    # a price that applies to every warehouse
    candidates.append(("price list", {"warehouse": ["in", ["", None]]}))
    # last resort: any price on this list. Prices are often stored against a
    # single stocking point, and a caller with no warehouse context should still
    # get a number rather than an error. `matched_on` records that it was loose.
    candidates.append(("any warehouse", {}))

    for label, extra in candidates:
        filters = {"item_code": item_code, "price_list": price_list, "selling": 1}
        filters.update(extra)
        row = _first_valid_price(filters, txn_date)
        if row:
            return {"rate": flt(row.price_list_rate), "matched_on": label, "item_price": row.name}

    frappe.throw(
        _("No price found for {0} on price list {1}.").format(
            frappe.bold(item_code), frappe.bold(price_list)
        ),
        PriceNotFound,
    )


def _first_valid_price(filters: dict, txn_date: str):
    rows = frappe.get_all(
        "Item Price",
        filters=filters,
        fields=["name", "price_list_rate", "valid_from", "valid_upto"],
        order_by="modified desc",
        ignore_permissions=True,
    )
    for row in rows:
        if row.valid_from and str(row.valid_from) > str(txn_date):
            continue
        if row.valid_upto and str(row.valid_upto) < str(txn_date):
            continue
        return row
    return None


# ---------------------------------------------------------------- rules


def clear_pricing_rule_cache(doc=None, method=None):
    """Invalidate the request-scoped Pricing Rule cache below.

    Registered on Pricing Rule's on_update/on_trash (see hooks.py) so a
    change takes effect on the very next price lookup - including within
    the same request, where frappe.local would otherwise keep serving a
    stale snapshot from before the edit.
    """
    if hasattr(frappe.local, "field_sales_pricing_rules"):
        del frappe.local.field_sales_pricing_rules


def _active_selling_rules() -> list[dict]:
    """Every enabled selling Pricing Rule, with its item-code restriction (if
    any) attached as ``_item_codes`` - fetched once and cached for the rest
    of this request.

    calculate_rate runs once per order line, and enforce_sales_order_rates
    calls it for every line on every save. With ~1,200 active rules in
    production, re-running this same unfiltered `frappe.get_all` plus one
    extra `Pricing Rule Item Code` query *per rule* on every single call
    turned adding a handful of items to an order into several thousand
    queries. None of that work depends on which item is being priced, so it
    only needs to happen once per request, not once per line.
    """
    cached = getattr(frappe.local, "field_sales_pricing_rules", None)
    if cached is not None:
        return cached

    rules = frappe.get_all(
        "Pricing Rule",
        filters={"disable": 0, "selling": 1},
        fields=[
            "name", "title", "priority", "rate_or_discount", "rate",
            "discount_percentage", "discount_amount", "min_qty", "max_qty",
            "warehouse", "valid_from", "valid_upto",
            "custom_delivery_term", "custom_payment_terms_template",
        ],
        ignore_permissions=True,
    )

    item_codes_by_rule: dict[str, set] = {}
    if rules:
        for row in frappe.get_all(
            "Pricing Rule Item Code",
            filters={"parent": ["in", [r.name for r in rules]]},
            fields=["parent", "item_code"],
            ignore_permissions=True,
        ):
            item_codes_by_rule.setdefault(row.parent, set()).add(row.item_code)

    for rule in rules:
        # None means "no item restriction, applies to every item"
        rule["_item_codes"] = item_codes_by_rule.get(rule.name)

    frappe.local.field_sales_pricing_rules = rules
    return rules


def find_pricing_rules(
    item_code: str,
    qty: float = 1,
    warehouse: str | None = None,
    delivery_term: str | None = None,
    payment_terms_template: str | None = None,
    transaction_date: str | None = None,
) -> list[dict]:
    """Selling Pricing Rules that match this context, highest priority first.

    Matching is on explicit fields only. A rule that names a delivery term or
    payment term applies only when that term is selected; a rule that names
    neither is context-neutral and always applies.
    """
    txn_date = transaction_date or nowdate()
    warehouses = warehouse_chain(warehouse)

    matched = []
    for rule in _active_selling_rules():
        if rule.valid_from and str(rule.valid_from) > str(txn_date):
            continue
        if rule.valid_upto and str(rule.valid_upto) < str(txn_date):
            continue
        if rule.warehouse and warehouses and rule.warehouse not in warehouses:
            continue
        if rule.warehouse and not warehouses:
            continue
        if flt(rule.min_qty) and flt(qty) < flt(rule.min_qty):
            continue
        if flt(rule.max_qty) and flt(qty) > flt(rule.max_qty):
            continue
        # context axes: a rule that names a term only applies to that term
        if rule.custom_delivery_term and rule.custom_delivery_term != delivery_term:
            continue
        if (
            rule.custom_payment_terms_template
            and rule.custom_payment_terms_template != payment_terms_template
        ):
            continue
        if rule["_item_codes"] is not None and item_code not in rule["_item_codes"]:
            continue
        matched.append(rule)

    matched.sort(key=lambda r: cint(r.priority), reverse=True)
    return matched


def apply_rule(rate: float, rule: dict) -> tuple[float, float]:
    """Return (new_rate, adjustment)."""
    rate = flt(rate)
    kind = rule.get("rate_or_discount")

    if kind == "Rate" and flt(rule.get("rate")):
        new_rate = flt(rule["rate"])
    elif kind == "Discount Percentage" and flt(rule.get("discount_percentage")):
        new_rate = rate * (1 - flt(rule["discount_percentage"]) / 100.0)
    elif kind == "Discount Amount" and flt(rule.get("discount_amount")):
        new_rate = rate - flt(rule["discount_amount"])
    else:
        return rate, 0.0

    new_rate = max(flt(new_rate, 2), 0.0)
    return new_rate, flt(new_rate - rate, 2)


# ---------------------------------------------------------------- public


def calculate_rate(
    item_code: str,
    customer: str | None = None,
    qty: float = 1,
    warehouse: str | None = None,
    price_list: str | None = None,
    delivery_term: str | None = None,
    payment_terms_template: str | None = None,
    transaction_date: str | None = None,
    customer_type: str | None = None,
) -> dict:
    """The single entry point for a line rate."""
    resolved_type = resolve_customer_type(customer, customer_type)
    price_list = resolve_price_list(customer, resolved_type, price_list)
    base = get_base_rate(
        item_code=item_code,
        price_list=price_list,
        warehouse=warehouse,
        transaction_date=transaction_date,
    )

    rate = base["rate"]
    applied = []
    for rule in find_pricing_rules(
        item_code=item_code,
        qty=qty,
        warehouse=warehouse,
        delivery_term=delivery_term,
        payment_terms_template=payment_terms_template,
        transaction_date=transaction_date,
    ):
        rate, adjustment = apply_rule(rate, rule)
        if adjustment:
            applied.append(
                {
                    "rule": rule["name"],
                    "title": rule.get("title") or rule["name"],
                    "adjustment": adjustment,
                }
            )

    return {
        "item_code": item_code,
        "base_rate": base["rate"],
        "final_rate": flt(rate, 2),
        "matched_on": base["matched_on"],
        "customer_type": resolved_type,
        "pricing_rules_applied": applied,
        "price_list": price_list,
    }


@frappe.whitelist()
def get_rate(
    item_code: str,
    customer: str | None = None,
    qty: float = 1,
    warehouse: str | None = None,
    delivery_term: str | None = None,
    payment_terms_template: str | None = None,
):
    """Whitelisted wrapper for the client."""
    return calculate_rate(
        item_code=item_code,
        customer=customer,
        qty=flt(qty) or 1,
        warehouse=warehouse,
        delivery_term=delivery_term,
        payment_terms_template=payment_terms_template,
    )


# ---------------------------------------------------------------- enforcement


def enforce_sales_order_rates(doc, method=None):
    """Recompute every line on the server, whatever the client sent.

    Registered on Sales Order `validate`, so it runs for the desk UI, the REST
    API and the mobile client alike. A submitted rate is a suggestion; the
    server decides. This is the control the original app was missing - it had
    an equivalent function but never registered it, so a client could book an
    order at any price it liked.
    """
    if not doc.get("customer") or doc.get("fs_skip_pricing"):
        return

    for item in doc.get("items") or []:
        if not item.get("item_code"):
            continue
        if cint(item.get("custom_manual_rate_override")):
            # deliberate override, recorded on the row
            continue

        try:
            result = calculate_rate(
                item_code=item.item_code,
                customer=doc.customer,
                qty=flt(item.qty) or 1,
                warehouse=item.get("warehouse") or doc.get("set_warehouse"),
                price_list=doc.get("selling_price_list"),
                delivery_term=doc.get("custom_delivery_term"),
                payment_terms_template=doc.get("payment_terms_template"),
                transaction_date=str(doc.get("transaction_date") or nowdate()),
            )
        except PriceNotFound:
            # No Item Price exists at all - the only number left to book
            # against is whatever rate the rep typed on the line itself
            # (Sales Order Item.rate - the standard field, nothing custom).
            # This can't be used to undercut a price that does exist: every
            # other branch below overwrites the client's rate the moment a
            # real price is found (submitted != computed), so a manual rate
            # only ever survives when calculate_rate has already raised.
            manual_rate = flt(item.get("rate"))
            if manual_rate > 0:
                result = {"base_rate": None, "final_rate": manual_rate, "pricing_rules_applied": []}
            else:
                frappe.throw(
                    frappe._(
                        "{0} has no price on file for {1}. Enter a rate for "
                        "this line manually, or remove the item."
                    ).format(item.item_code, doc.customer),
                    PriceNotFound,
                )

        submitted = flt(item.rate)
        computed = flt(result["final_rate"])

        if item.meta.has_field("custom_base_rate"):
            item.custom_base_rate = result["base_rate"]
        if item.meta.has_field("custom_computed_rate"):
            item.custom_computed_rate = computed
        if item.meta.has_field("custom_pricing_rules_applied"):
            item.custom_pricing_rules_applied = json.dumps(result["pricing_rules_applied"])

        if submitted != computed:
            item.rate = computed
            item.price_list_rate = result["base_rate"]

    # our rates are final; stop ERPNext recomputing over the top
    doc.ignore_pricing_rule = 1


def restore_native_pricing_rules_field(doc, method=None):
    """Mirror our own result onto Sales Order Item's native `pricing_rules`
    field, so the standard desk item grid's "view applied pricing rules"
    icon and any report/consumer reading that field directly (rather than
    our own custom_pricing_rules_applied) still works.

    Registered on `before_save`, separately from enforce_sales_order_rates
    on `before_validate`. ERPNext's own accounts_controller.validate() -> is
    called between those two events, and calls set_missing_item_details()
    unconditionally (not gated on ignore_pricing_rule - see
    accounts_controller.py's set_missing_values). That path reaches
    get_pricing_rule_for_item, which - specifically because we've set
    ignore_pricing_rule=1 - takes the branch that calls
    remove_pricing_rule_for_item and blanks the field straight back out.
    So anything written to `pricing_rules` during before_validate is always
    gone by the time validate() finishes; before_save runs after that, once
    ERPNext's own clearing is done, so the value written here survives.
    Same shape ERPNext itself writes: a JSON array of rule names, or "" when
    none matched - taken from custom_pricing_rules_applied, already computed.
    """
    for item in doc.get("items") or []:
        if not item.meta.has_field("pricing_rules"):
            continue
        applied = frappe.parse_json(item.get("custom_pricing_rules_applied") or "[]")
        rule_names = [r["rule"] for r in applied]
        item.pricing_rules = frappe.as_json(rule_names) if rule_names else ""
