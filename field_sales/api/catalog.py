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
from frappe.utils import cint, flt

from field_sales import pricing, scope
from field_sales.api.listing import ListConfig, paginated_list

ITEM_CONFIG = ListConfig(
    doctype="Item",
    fields=["name", "item_code", "item_name", "item_group", "stock_uom",
            "description", "image", "disabled"],
    search_fields=["item_code", "item_name", "description"],
    filter_fields={"item_group": "item_group", "disabled": "disabled"},
    territory_field=None,
    owner_field=None,
    default_order="item_name asc",
    sortable_fields=["item_code", "item_name", "item_group"],
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
    owner_field=None,
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

    page = paginated_list(ITEM_CONFIG, form=form)

    resolved_list = pricing.resolve_price_list(
        customer, pricing.resolve_customer_type(customer, explicit=customer_type)
    )

    for row in page["records"]:
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
        except pricing.PriceNotFound:
            row["rate"] = None
            row["base_rate"] = None
            row["price_matched_on"] = None

    page["price_list"] = resolved_list
    page["customer"] = customer
    return page


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
    """Stocking points a rep may order from."""
    return frappe.get_all(
        "Warehouse",
        filters={"disabled": 0, "is_group": 0},
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

# item_code / qty / uom only - never rate, price_list_rate or amount. Those
# are recomputed server side by enforce_sales_order_rates regardless of what
# is appended here.
ORDER_WRITABLE_ITEM_FIELDS = {
    "item_code",
    "qty",
    "uom",
    "warehouse",
    "delivery_date",
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


@frappe.whitelist(methods=["POST"])
def submit_order(name: str):
    """Submit a reviewed order."""
    doc = frappe.get_doc("Sales Order", name)
    doc.check_permission("submit")
    with _as_a_privileged_user():
        doc.flags.ignore_permissions = True
        doc.submit()
    return {"name": doc.name, "docstatus": doc.docstatus, "grand_total": doc.grand_total}
