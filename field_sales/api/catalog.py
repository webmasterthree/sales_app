# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Products, prices and orders for the field client.

Replaces api/price_list.py (4 string-formatted SQL sites, all four reachable
from user input) and the read side of api/sales_order.py.

Prices come from field_sales.pricing, so the app shows the same number the
server will store on an order - which was not true before, because the client
displayed one rate and then sent whatever it liked.
"""

import contextlib

import frappe
from frappe.utils import add_days, cint, flt, nowdate

from field_sales import pricing, scope
from field_sales.api.listing import ListConfig, paginated_list

ITEM_CONFIG = ListConfig(
    doctype="Item",
    fields=["name", "item_code", "item_name", "item_group", "stock_uom",
            "description", "image", "disabled", "has_variants"],
    search_fields=["item_code", "item_name", "description"],
    filter_fields={"item_group": "item_group", "disabled": "disabled"},
    territory_field=None,
    owner_field=None,
    default_order="item_name asc",
    sortable_fields=["item_code", "item_name", "item_group"],
    # A template (has_variants=1, e.g. "Rasgulla") is never itself sellable -
    # only its variants ("500g Pack", "1kg Pack", ...) are actually priced
    # and stocked, so it never carries a real Item Price of its own and
    # would only ever show up as a dead "Unpriced" row in a flat catalogue.
    # This is the default for every generic item lookup (Price List screen,
    # Sample/Complaint item pickers, ...); the Sales Order item picker's
    # first step needs the opposite shape - product families before their
    # variants - and uses the dedicated item_templates() below instead.
    base_filters={"has_variants": 0},
)

ORDER_CONFIG = ListConfig(
    doctype="Sales Order",
    fields=["name", "customer", "customer_name", "transaction_date",
            "delivery_date", "status", "grand_total", "currency",
            "territory", "fs_field_visit", "docstatus", "contact_mobile"],
    search_fields=["name", "customer_name"],
    filter_fields={
        "status": "status",
        "customer": "customer",
        "territory": "territory",
        "transaction_date": "transaction_date",
        "field_visit": "fs_field_visit",
    },
    territory_field="territory",
    owner_field="created_by_emp",
    default_order="transaction_date desc",
    sortable_fields=["name", "transaction_date", "delivery_date",
                     "customer_name", "grand_total", "status"],
    tabs={
        "draft": {"docstatus": 0},
        "submitted": {"docstatus": 1},
        "to_deliver": {"status": ["in", ["To Deliver", "To Deliver and Bill"]]},
        "completed": {"status": "Completed"},
    },
)


@frappe.whitelist()
def item_list():
    """The product catalogue, without prices."""
    return paginated_list(ITEM_CONFIG)


@frappe.whitelist()
def item_list_by_segment(segment: str, search_text: str | None = None, limit: int = 20):
    """Items tagged with a real Segment (via Item's own Segment Mapping
    child table) - for the pitched-items picker, once a rep has chosen
    which segment a visit's pitch is about. `segment` is passed through
    frappe.get_all's parameterised filters, never interpolated into SQL.
    """
    if not frappe.has_permission("Item", "read"):
        raise frappe.PermissionError
    or_filters = None
    if search_text:
        or_filters = [
            ["item_code", "like", f"%{search_text}%"],
            ["item_name", "like", f"%{search_text}%"],
        ]
    return frappe.get_all(
        "Item",
        filters=[["Segment Mapping", "segment", "=", segment], ["disabled", "=", 0]],
        or_filters=or_filters,
        fields=["name", "item_code", "item_name", "stock_uom"],
        order_by="item_name asc",
        limit_page_length=cint(limit) or 20,
    )


@frappe.whitelist()
def item_templates(customer: str | None = None, warehouse: str | None = None,
                   customer_type: str | None = None, search_text: str | None = None,
                   limit: int = 15):
    """Product families before their variants - templates and standalone
    items, never a bare variant - for the Sales Order item picker's first
    step, where the rep picks a *product* and only then (if it has variants)
    which specific pack/size. This is the opposite shape from a flat
    catalogue browse (price_list/item_list), which wants every real
    orderable SKU - i.e. variants, not their unpriced template parent.

    A template row is priced here too, even though it can never resolve a
    real rate (calculate_rate always raises PriceNotFound for one) - the
    caller uses has_variants to render it as "choose a variant" rather than
    a price, the same way item_variants' own rows get priced.
    """
    if not frappe.has_permission("Item", "read"):
        raise frappe.PermissionError
    or_filters = None
    if search_text:
        or_filters = [
            ["item_code", "like", f"%{search_text}%"],
            ["item_name", "like", f"%{search_text}%"],
        ]
    records = frappe.get_all(
        "Item",
        filters={"disabled": 0, "variant_of": ["is", "not set"]},
        or_filters=or_filters,
        fields=["name", "item_code", "item_name", "item_group", "stock_uom", "has_variants"],
        order_by="item_name asc",
        limit_page_length=cint(limit) or 15,
    )
    _attach_prices(records, customer, warehouse, customer_type)
    return records


@frappe.whitelist()
def price_list(customer: str | None = None, warehouse: str | None = None,
               item_group: str | None = None, search_text: str | None = None,
               customer_type: str | None = None,
               limit: int = 50, current_page: int = 1):
    """Sellable items with the rate this customer would actually get.

    Rates are resolved through the same engine that prices an order, so what a
    rep quotes is what the order will carry.

    ``customer_type`` (DL/DP) lets the caller preview dealer-versus-distributor
    pricing without having a specific customer selected yet - the Flutter app's
    price list screen offers this as its own filter, separate from picking a
    customer. When a customer *is* given, its own recorded type still wins
    (see ``pricing.resolve_customer_type``); this only fills the gap where
    there is no customer to read it from.
    """
    if not frappe.has_permission("Item", "read"):
        raise frappe.PermissionError

    form = {"limit": limit, "current_page": current_page, "disabled": 0}
    if item_group:
        form["item_group"] = item_group
    if search_text:
        form["search_text"] = search_text

    # Resolved up front (rather than inside _attach_prices, as before) so an
    # item with no Item Price row on this exact list can be excluded from
    # the list itself - a rep browsing prices has no use for a row that will
    # only ever read "Unpriced", and a real order can't be booked with it
    # anyway (enforce_sales_order_rates raises PriceNotFound). Scoping the
    # underlying Item query to only priced item codes keeps pagination
    # correct, rather than filtering the page's rows after the fact and
    # silently returning fewer than `limit` results.
    resolved_list = pricing.resolve_price_list(
        customer, pricing.resolve_customer_type(customer, explicit=customer_type)
    )
    priced_codes = frappe.get_all(
        "Item Price",
        filters={"price_list": resolved_list, "selling": 1},
        pluck="item_code",
    )
    priced_only = ListConfig(
        doctype=ITEM_CONFIG.doctype,
        fields=ITEM_CONFIG.fields,
        search_fields=ITEM_CONFIG.search_fields,
        filter_fields=ITEM_CONFIG.filter_fields,
        territory_field=ITEM_CONFIG.territory_field,
        owner_field=ITEM_CONFIG.owner_field,
        default_order=ITEM_CONFIG.default_order,
        sortable_fields=ITEM_CONFIG.sortable_fields,
        base_filters={**ITEM_CONFIG.base_filters, "item_code": ["in", list(set(priced_codes)) or [""]]},
    )

    page = paginated_list(priced_only, form=form)
    page["price_list"] = _attach_prices(page["records"], customer, warehouse, customer_type, resolved_list)
    page["customer"] = customer
    return page


def _attach_prices(records: list[dict], customer, warehouse, customer_type,
                   resolved_list: str | None = None) -> str:
    """Price each row the same way an order line would be priced, so what a
    rep sees here is what the order will actually carry. Returns the price
    list that was resolved and used."""
    resolved_list = resolved_list or pricing.resolve_price_list(
        customer, pricing.resolve_customer_type(customer, explicit=customer_type)
    )
    for row in records:
        try:
            result = pricing.calculate_rate(
                item_code=row["item_code"],
                customer=customer,
                warehouse=warehouse,
                price_list=resolved_list,
            )
            row["rate"] = result["final_rate"]
            row["base_rate"] = result["base_rate"]
            row["price_matched_on"] = result["matched_on"]
            row["pricing_rules_applied"] = result["pricing_rules_applied"]
        except pricing.PriceNotFound:
            row["rate"] = None
            row["base_rate"] = None
            row["price_matched_on"] = None
            row["pricing_rules_applied"] = []
    return resolved_list


@frappe.whitelist()
def item_variants(template: str, customer: str | None = None, warehouse: str | None = None,
                  customer_type: str | None = None, search_text: str | None = None,
                  limit: int = 50):
    """Sellable variants of an item template (has_variants=1), priced the
    same way price_list is. The item-selection screen shows templates first;
    picking one drills in here rather than adding the template itself,
    since a template row is never something a Sales Order line can carry."""
    if not frappe.has_permission("Item", "read"):
        raise frappe.PermissionError

    or_filters = None
    if search_text:
        or_filters = [
            ["item_code", "like", f"%{search_text}%"],
            ["item_name", "like", f"%{search_text}%"],
        ]
    records = frappe.get_all(
        "Item",
        filters={"variant_of": template, "disabled": 0},
        or_filters=or_filters,
        fields=["name", "item_code", "item_name", "item_group", "stock_uom", "image"],
        order_by="item_name asc",
        limit_page_length=cint(limit) or 50,
    )

    price_list_used = _attach_prices(records, customer, warehouse, customer_type)
    return {"records": records, "template": template, "price_list": price_list_used}


@frappe.whitelist()
def item_price(item_code: str, customer: str | None = None,
               warehouse: str | None = None, qty: float = 1,
               delivery_term: str | None = None,
               payment_terms_template: str | None = None):
    """The rate for one line, with the rules that produced it."""
    return pricing.calculate_rate(
        item_code=item_code,
        customer=customer,
        qty=flt(qty) or 1,
        warehouse=warehouse,
        delivery_term=delivery_term,
        payment_terms_template=payment_terms_template,
    )


@frappe.whitelist()
def order_list():
    return paginated_list(ORDER_CONFIG)


@frappe.whitelist()
def order(name: str):
    doc = frappe.get_doc("Sales Order", name)
    doc.check_permission("read")
    return doc.as_dict()


@frappe.whitelist()
def warehouses():
    """Stocking points a rep may order from, scoped to their own company.

    Only the regional/city *group* warehouses show here (Kolkata, Dankuni,
    Patna, ...), not every granular leaf under them (Cold Room, Amazon
    warehouse Kolkata, transit godowns, ...) - a rep picks the depot they
    work out of, not a specific internal shelf. The company's own synthetic
    tree root ("All Warehouses - <abbr>", created automatically by ERPNext
    for every company and itself a group with no parent) is excluded too -
    it is not a real depot, just the top of the tree.

    Spec: "Warehouse list should show only allowed warehouses." The obvious
    match for "allowed" elsewhere in this app is field_sales.scope's
    territory tree - fmcg.api's channel-partner flow lists Channel Partner
    Warehouse that way (it carries its own ``territory`` field). The native
    Warehouse doctype has no such field and nothing links a Warehouse to a
    Territory anywhere in this data model (checked: Warehouse's own fields
    are stock/accounting ones - company, account, parent_warehouse - not
    geography), so reusing scope.territory_filter here would mean inventing a
    link the data doesn't have, not applying an existing one.

    What Warehouse *does* carry, and what already gates a rep's order in
    _resolve_order_context (company, cost_center, shop are all resolved from
    the rep's own Employee.company), is ``company``. A rep whose Employee
    record puts them at Company A has no legitimate reason to book stock out
    of Company B's warehouse - that boundary already exists in this app, so
    scoping the warehouse list to the rep's own company closes the same gap
    the spec is pointing at without fabricating a territory link. A rep with
    no resolvable company sees nothing, rather than every warehouse in the
    system, so the failure mode is an empty list, not an unscoped one -
    matching how field_sales.scope.territory_filter treats a scoped user with
    no territory of their own.

    An unrestricted user (Administrator, System Manager, Sales Master
    Manager - see scope.has_unrestricted_scope) still sees every group
    warehouse, the same carve-out every other scoped list in this app makes.
    """
    filters = {"disabled": 0, "is_group": 1, "parent_warehouse": ["is", "set"]}

    if not scope.has_unrestricted_scope():
        employee = _own_employee()
        company = (
            frappe.db.get_value("Employee", employee, "company")
            if employee else None
        ) or frappe.defaults.get_global_default("company")
        if not company:
            return []
        filters["company"] = company

    return frappe.get_all(
        "Warehouse",
        filters=filters,
        fields=["name", "warehouse_name"],
        order_by="warehouse_name asc",
    )


@frappe.whitelist()
def order_options():
    """Reference values used by the Sales Order registration step."""
    if not frappe.has_permission("Sales Order", "read"):
        raise frappe.PermissionError

    return {
        "warehouses": warehouses(),
        "delivery_terms": frappe.get_all(
            "Delivery Term",
            fields=["name", "delivery_term"],
            order_by="delivery_term asc",
        ) if frappe.db.exists("DocType", "Delivery Term") else [],
        "payment_terms": frappe.get_all(
            "Payment Terms Template",
            fields=["name", "template_name"],
            order_by="template_name asc",
        ),
    }


# ---------------------------------------------------------------- write path
#
# Modelled on api/field_visit.py: an explicit allow-list of client-writable
# fields, the server decides everything else. The one field that matters most
# here - the rate on every line - is not on this list at all, because it is
# not decided here. field_sales.pricing.enforce_sales_order_rates is
# registered on Sales Order.before_validate (see hooks.py) and recomputes
# every line rate from field_sales.pricing.calculate_rate - the same function
# item_price above calls - discarding whatever the client sent. A client that
# submits a fake rate gets its own number silently overwritten on insert, not
# an error; the point is that the number it saw in the app (from item_price)
# is the number that ends up on the order.

ORDER_WRITABLE_FIELDS = {
    "customer",
    "transaction_date",
    "delivery_date",
    "po_no",
    "customer_address",
    "shipping_address_name",
    "contact_person",
    "remarks",
    "fs_field_visit",
    "set_warehouse",
    "custom_delivery_term",
    "payment_terms_template",
}

# item_code / qty / uom mostly - never price_list_rate or amount, and rate
# is never TRUSTED, only ever used as a last resort. enforce_sales_order_rates
# recomputes every rate server-side regardless of what's sent here, and
# overwrites it outright whenever a real price is found - a client-sent rate
# only ever survives when calculate_rate has already raised PriceNotFound
# for that item, i.e. there's genuinely no price on file to undercut. See
# pricing.py's enforce_sales_order_rates.
ORDER_WRITABLE_ITEM_FIELDS = {
    "item_code",
    "qty",
    "uom",
    "warehouse",
    "delivery_date",
    "rate",
}


def _apply_order_payload(doc, payload: dict) -> None:
    for key, value in (payload or {}).items():
        if key in ORDER_WRITABLE_FIELDS:
            doc.set(key, value)

    if "items" in (payload or {}):
        rows = payload.get("items") or []
        if isinstance(rows, str):
            rows = frappe.parse_json(rows)
        doc.set("items", [])
        for row in rows:
            doc.append(
                "items",
                {k: v for k, v in (row or {}).items() if k in ORDER_WRITABLE_ITEM_FIELDS},
            )


def _own_employee() -> str | None:
    return frappe.db.get_value(
        "Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
    )


@contextlib.contextmanager
def _as_a_privileged_user():
    """Run the persist step as Administrator, once we have already decided
    the write is allowed.

    ERPNext's Sales Order controller separately checks read/select on the
    customer's receivable Account while filling in payment defaults - a check
    that is independent of ``ignore_permissions`` and unrelated to anything a
    field rep role should have to hold. Authorization for this endpoint has
    already happened above: the explicit ``frappe.has_permission``/
    ``check_permission`` call, and the allow-list that decides exactly which
    fields the client could set. This only widens the identity the write is
    performed under, not what is written or who is allowed to ask for it.
    """
    current = frappe.session.user
    frappe.set_user("Administrator")
    try:
        yield
    finally:
        frappe.set_user(current)


def _resolve_order_context(doc, employee: str) -> None:
    """Fields the server decides, never the client: company, shop, territory,
    who filed it, and which price list it is priced against."""
    doc.order_type = doc.order_type or "Sales"

    doc.company = (
        frappe.db.get_value("Employee", employee, "company")
        or frappe.defaults.get_global_default("company")
    )
    doc.cost_center = doc.cost_center or frappe.get_cached_value(
        "Company", doc.company, "cost_center"
    )

    if doc.meta.has_field("created_by_emp"):
        doc.created_by_emp = employee
    if doc.meta.has_field("created_by_name"):
        doc.created_by_name = frappe.db.get_value("Employee", employee, "employee_name")

    # contact_mobile has no fetch_from of its own on this doctype - a real
    # gap that meant every order ever created here left it blank
    # regardless of which contact was actually picked, silently breaking
    # anything that reads it (a WhatsApp order-confirmation rule included).
    if doc.get("contact_person") and not doc.get("contact_mobile"):
        doc.contact_mobile = frappe.db.get_value("Contact", doc.contact_person, "mobile_no")

    # A second fallback for the same gap: an order created directly in Desk
    # (bypassing this API's own contact_person handling above) can reach
    # here with both contact_person and contact_mobile still blank. The
    # Customer's own mobile_no field (fetch_from: customer_primary_contact.
    # mobile_no) is already reliably maintained independent of any one
    # order, so use it rather than leaving the order with no number at all.
    if not doc.get("contact_mobile"):
        doc.contact_mobile = frappe.db.get_value("Customer", doc.customer, "mobile_no")

    shop = frappe.db.get_value("Customer", doc.customer, "custom_shop")
    if not shop:
        frappe.throw(
            frappe._(
                "{0} has no shop configured, so an order cannot be booked "
                "against it. Ask an administrator to set the shop on that customer."
            ).format(doc.customer)
        )
    doc.shop = shop

    doc.territory = scope.resolve_leaf_territory(
        doc.get("territory"), employee=employee, fallback_user=frappe.session.user
    )

    doc.selling_price_list = pricing.resolve_price_list(
        doc.customer, pricing.resolve_customer_type(doc.customer)
    )

    _resolve_channel_partner(doc)

    # Attribute the order to the filing rep via ERPNext's own Sales Team
    # table - the doctype has no direct "which rep filed this" field, and a
    # client-supplied one wasn't trustworthy anyway. Without this row, the
    # order exists but counts against nobody's target or leaderboard total,
    # which is exactly the gap that left `field_sales.api.home.leaderboard`
    # and `sales_target` reading real order data but always landing on zero.
    sales_person = frappe.db.get_value("Sales Person", {"employee": employee}, "name")
    if sales_person and not doc.get("sales_team"):
        doc.append("sales_team", {
            "sales_person": sales_person,
            "allocated_percentage": 100,
        })

    _resolve_gst(doc)


def _resolve_channel_partner(doc) -> None:
    """customer_level/custom_channel_partner mirror the *customer's own*
    master-data classification, the same as field_visit.py's and
    field_trial_plan.py's identical derivation - see set_channel_partner on
    either for the full reasoning. These are real fields fmcg_cp already
    adds to the native Sales Order doctype (customer_level, custom_channel_partner,
    cp_name), guarded with has_field since a deployment without that app
    installed simply has nothing to set here.

    Not in ORDER_WRITABLE_FIELDS at all - a client can't set these directly,
    only the Customer picked for the order decides them.
    """
    if not doc.meta.has_field("customer_level") or not doc.customer:
        return
    level, channel_partner = frappe.db.get_value(
        "Customer", doc.customer, ["customer_level", "custom_channel_partner"]
    ) or (None, None)
    doc.customer_level = level or "Primary"
    if doc.meta.has_field("custom_channel_partner"):
        doc.custom_channel_partner = channel_partner or None


def _resolve_gst(doc) -> None:
    """Populate the GST tax template and its rows on ``doc.taxes``, the same
    way india_compliance does when the Desk form's customer/address trigger
    fires - which never happens here, since this endpoint sets customer and
    customer_address itself before validate ever runs.

    Confirmed root cause of orders silently carrying zero GST: india_compliance's
    ``get_gst_details`` refuses to resolve any tax template unless
    ``doc.company_gstin`` is already set - a field the Desk form's own JS
    fills in from the Company master the moment a company/warehouse is
    picked, but that never happens on a document built by this endpoint,
    since nothing here ever touches that field. Without a resolved template,
    ``taxes`` stays empty, and india_compliance's own GST treatment logic
    (``update_item_gst_treatment.set_for_no_taxes``) then stamps every line
    Nil-Rated whenever it sees an empty ``taxes`` table - zeroing the order's
    tax regardless of what each item's own Item Tax Template says.
    """
    try:
        from india_compliance.gst_india.overrides.transaction import get_gst_details
    except ImportError:
        return
    if not doc.meta.has_field("taxes_and_charges"):
        return
    if doc.meta.has_field("company_gstin") and not doc.get("company_gstin"):
        doc.company_gstin = frappe.get_cached_value("Company", doc.company, "gstin")
    gst_details = get_gst_details(doc.as_dict(), doc.doctype, doc.company, update_place_of_supply=True)
    if gst_details:
        doc.update(gst_details)


@frappe.whitelist(methods=["POST"])
def create_order(**payload):
    """Start a draft Sales Order. The rep is always the signed in user's own
    employee; the price list, shop and territory are derived, never taken
    from the client; and every line rate is recomputed on insert by
    enforce_sales_order_rates regardless of what is sent here."""
    if not frappe.has_permission("Sales Order", "create"):
        raise frappe.PermissionError

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    employee = _own_employee()
    if not employee:
        frappe.throw(
            frappe._(
                "Your user account is not linked to an active Employee, so an "
                "order cannot be filed against you. Ask an administrator to set "
                "the User ID on your Employee record."
            )
        )

    if not (payload or {}).get("customer"):
        frappe.throw(frappe._("Select the customer this order is for."))

    doc = frappe.new_doc("Sales Order")
    _apply_order_payload(doc, payload)
    _resolve_order_context(doc, employee)
    with _as_a_privileged_user():
        doc.insert(ignore_permissions=True)

    return {"name": doc.name, "docstatus": doc.docstatus, "grand_total": doc.grand_total}


@frappe.whitelist(methods=["POST"])
def update_order(name: str, **payload):
    """Edit a draft order. Re-derives the same server-owned context as create,
    so editing the customer cannot silently strand a stale shop, territory or
    price list from the previous customer."""
    doc = frappe.get_doc("Sales Order", name)
    doc.check_permission("write")

    if doc.docstatus != 0:
        frappe.throw(frappe._("Only a draft order can be edited."))

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    employee = _own_employee()
    _apply_order_payload(doc, payload)
    if employee:
        _resolve_order_context(doc, employee)
    with _as_a_privileged_user():
        doc.save(ignore_permissions=True)

    return {"name": doc.name, "docstatus": doc.docstatus, "grand_total": doc.grand_total}


def _prepare_visit_conversion(visit_name: str) -> dict:
    """Shared guards + pricing for turning a completed Field Visit into a
    Sales Order - used by both ``visit_order_prefill`` (read-only, for the
    rep to review on the order form before saving anything) and
    ``convert_visit_to_order`` (kept for any caller that still wants the old
    create-immediately behaviour).

    Spec: "Visit can be converted into Sales Order if allowed." "If allowed"
    is enforced here, not just hinted at in the UI:

    * the visit must be submitted (docstatus 1) - a draft's customer and
      outcome can still change, so nothing durable should be built from it
      yet;
    * its party must be a real Customer, not a Prospect - a Sales Order has
      no concept of a prospect party, and a Prospect visit has to go through
      the app's own lead/customer conversion first;
    * order_status must not be "Without Order" - the rep has already recorded
      that this visit did not produce an order (see FieldVisit.validate_outcome
      / the mandatory ``reason``), and converting it anyway would silently
      overwrite that record with the opposite outcome;
    * the visit must not already be linked from a live Sales Order - checked
      via the same ``fs_field_visit`` back-link ``order_options``/order create
      already populate, so the same visit cannot be converted twice.

    Pitched items are only ever a *starting point*: each pitched row carries
    whatever rate ``field_sales.pricing.calculate_rate`` can resolve for it,
    or ``None`` when it can't - the same "no price on file, enter one
    manually" gap the order form's item picker already surfaces for a
    manually-added item, so an unpriced pitched item gets the identical
    manual-rate prompt instead of silently vanishing (or blocking the whole
    conversion, when it happened to be the visit's only pitched item). A
    visit with no pitched items at all has nothing to safely start an order
    from, and is refused rather than handed back an empty draft.
    """
    visit = frappe.get_doc("Field Visit", visit_name)
    visit.check_permission("read")

    if not frappe.has_permission("Sales Order", "create"):
        raise frappe.PermissionError

    if visit.docstatus != 1:
        frappe.throw(frappe._("Only a submitted visit can be converted into an order."))

    if visit.party_type != "Customer" or not visit.customer:
        frappe.throw(frappe._(
            "This visit has no linked Customer, so it cannot become a Sales "
            "Order. Convert the prospect to a Customer first."
        ))

    if visit.order_status == "Without Order":
        frappe.throw(frappe._(
            "This visit was recorded as not producing an order."
        ))

    if frappe.db.get_value("Customer", visit.customer, "customer_level") == "Secondary":
        frappe.throw(frappe._(
            "{0} is a Secondary customer, reached through its own channel "
            "partner - book this as a Channel Partner order instead."
        ).format(visit.customer))

    existing = frappe.db.exists(
        "Sales Order", {"fs_field_visit": visit.name, "docstatus": ["!=", 2]}
    )
    if existing:
        frappe.throw(frappe._(
            "Visit {0} has already been converted to Sales Order {1}."
        ).format(visit.name, existing))

    employee = _own_employee()
    if not employee:
        frappe.throw(
            frappe._(
                "Your user account is not linked to an active Employee, so an "
                "order cannot be filed against you. Ask an administrator to set "
                "the User ID on your Employee record."
            )
        )

    pitched = [row for row in (visit.get("pitched_items") or []) if row.item_code]
    if not pitched:
        frappe.throw(frappe._(
            "This visit has no pitched items, so there is nothing to start "
            "an order from. Create the order manually and link it to this "
            "visit using the visit picker on the order form instead."
        ))

    delivery_date = add_days(nowdate(), 7)
    rows, unpriced_codes = [], []
    for row in pitched:
        try:
            result = pricing.calculate_rate(item_code=row.item_code, customer=visit.customer,
                                             qty=flt(row.qty) or 1)
            rate = result["final_rate"]
        except pricing.PriceNotFound:
            rate = None
            unpriced_codes.append(row.item_code)
        rows.append({
            "item_code": row.item_code,
            "item_name": row.item_name or row.item_code,
            "qty": flt(row.qty) or 1,
            "uom": row.uom or None,
            "rate": rate,
        })

    remarks = (
        f"Converted from Field Visit {visit.name}. Quantities below are "
        f"copied from what was pitched during the visit - review and adjust "
        f"before submitting. Rates are recalculated by the server, not "
        f"carried over from the pitch."
    )
    if unpriced_codes:
        remarks += " No price on file yet for: " + ", ".join(unpriced_codes) + " - enter a rate manually."

    return {
        "visit": visit,
        "employee": employee,
        "delivery_date": delivery_date,
        "rows": rows,
        "remarks": remarks,
    }


@frappe.whitelist()
def visit_order_prefill(visit_name: str):
    """Everything the order form needs to start a draft from this visit,
    without creating anything yet - the rep reviews and edits on the real
    order form, and nothing is saved until they choose to. Same guards and
    pricing as ``convert_visit_to_order``, just read-only."""
    prepared = _prepare_visit_conversion(visit_name)
    visit = prepared["visit"]
    return {
        "customer": visit.customer,
        "contact_person": visit.get("contact_person") or None,
        "delivery_date": prepared["delivery_date"],
        "remarks": prepared["remarks"],
        "fs_field_visit": visit.name,
        "items": prepared["rows"],
    }


@frappe.whitelist()
def visit_customer_context(visit_name: str):
    """The same shape as ``api.customers.customer`` (contacts, addresses,
    primary-contact/address defaults), but authorized through the Field
    Visit rather than the Customer document's own permission.

    A Customer's own territory field ("Area" in the UI) is a separate,
    independently-maintained value from the territory a Field Visit is
    actually filed under (derived from the rep's own scope at visit time -
    see scope.resolve_leaf_territory) - the same kind of drift already
    documented for visit_type/customer_level elsewhere in this app. When
    the two disagree, a plain ``Customer.check_permission("read")`` blocks a
    rep from even loading the customer they were just permitted to log a
    submitted visit against. Once the visit itself checks out, that's
    already the real authorization for this specific customer - reusing it
    here rather than trusting the Customer's own (possibly stale) territory."""
    visit = frappe.get_doc("Field Visit", visit_name)
    visit.check_permission("read")

    if visit.party_type != "Customer" or not visit.customer:
        frappe.throw(frappe._("This visit has no linked Customer."))

    from field_sales.api.customers import customer as customer_detail

    with _as_a_privileged_user():
        return customer_detail(visit.customer)


@frappe.whitelist(methods=["POST"])
def convert_visit_to_order(visit_name: str):
    """Turn a completed Field Visit into a draft Sales Order immediately.

    Kept for any caller that wants the old create-on-call behaviour - the
    app's own "Convert to Order" action now goes through
    ``visit_order_prefill`` + the order form instead, so the rep reviews
    before anything is saved. See ``_prepare_visit_conversion`` for the
    shared guards/pricing both of these build on.

    Unlike ``visit_order_prefill``, this path inserts immediately with no
    review step, so there is nowhere for a rep to enter a manual rate - an
    unpriced pitched item is left off here (as it always was), and this is
    the one place that still refuses outright if that leaves nothing priced
    to insert.
    """
    prepared = _prepare_visit_conversion(visit_name)
    visit = prepared["visit"]
    delivery_date = prepared["delivery_date"]

    priced_rows = [row for row in prepared["rows"] if row["rate"] is not None]
    if not priced_rows:
        frappe.throw(frappe._(
            "This visit has no pitched items with a resolvable price, so "
            "there is nothing to start an order from. Use the order form's "
            "own visit conversion instead, which lets you enter a manual "
            "rate."
        ))

    doc = frappe.new_doc("Sales Order")
    doc.customer = visit.customer
    doc.fs_field_visit = visit.name
    doc.contact_person = visit.get("contact_person") or None
    doc.delivery_date = delivery_date
    doc.remarks = prepared["remarks"]
    for row in priced_rows:
        doc.append("items", {
            "item_code": row["item_code"],
            "qty": row["qty"],
            "uom": row["uom"],
            "delivery_date": delivery_date,
        })
    _resolve_order_context(doc, prepared["employee"])
    with _as_a_privileged_user():
        doc.insert(ignore_permissions=True)

    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist(methods=["POST"])
def submit_order(name: str):
    """Submit a reviewed order."""
    doc = frappe.get_doc("Sales Order", name)
    doc.check_permission("submit")
    # _as_a_privileged_user briefly elevates to Administrator below, so the
    # real acting user - needed by notify.py's on_submit hook to tell the
    # rep from their manager - has to be captured before that happens.
    doc.flags.notify_actor = frappe.session.user
    with _as_a_privileged_user():
        doc.flags.ignore_permissions = True
        doc.submit()
    return {"name": doc.name, "docstatus": doc.docstatus, "grand_total": doc.grand_total}


def ensure_contact_mobile(doc, method=None):
    """Sales Order doc_event (before_validate - see hooks.py), so this
    applies no matter how the order was created - the same fallback
    _resolve_order_context already runs for create_order/update_order's own
    callers, extended to cover a Sales Order made directly in Desk too
    (which never goes through this app's own API at all, and left a real
    order sitting with no phone number for anything - a WhatsApp order
    confirmation included - to send to)."""
    if doc.get("contact_mobile"):
        return
    if doc.get("contact_person"):
        doc.contact_mobile = frappe.db.get_value("Contact", doc.contact_person, "mobile_no")
    if not doc.get("contact_mobile") and doc.get("customer"):
        doc.contact_mobile = frappe.db.get_value("Customer", doc.customer, "mobile_no")
