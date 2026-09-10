# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Channel Partner orders - a rep booking a sale for a Secondary customer,
reached through that customer's own fixed channel partner.

This is a genuinely different doctype from the native Sales Order the Direct
Customer flow books (api/catalog.py): "Secondary Sales Order", owned by the
fmcg_cp app rather than field_sales or core ERPNext. It ships with no
permission for any field-rep role at all (only System Manager - granted back
via field_sales's own fixtures/custom_docperm.json, the same pattern already
used for Issue) and a controller that does nothing (`class
SecondarySalesOrder(Document): pass`) - no rate/amount calculation, no
derived territory/shop/created-by. Everything that pattern would normally get
for free from ERPNext's SellingController has to be done here explicitly,
mirroring catalog.py's own _resolve_order_context as closely as this
doctype's actual fields allow.
"""

import frappe
from frappe.utils import add_days, flt, nowdate

from field_sales import pricing, scope
from field_sales.api.listing import ListConfig, paginated_list

LIST_CONFIG = ListConfig(
    doctype="Secondary Sales Order",
    fields=[
        "name",
        "customer",
        "customer_name",
        "custom_channel_partner",
        "cp_name",
        "customer_level",
        "transaction_date",
        "delivery_date",
        "territory",
        "set_warehouse",
        "docstatus",
    ],
    search_fields=["name", "customer_name", "cp_name"],
    filter_fields={
        "customer": "customer",
        "territory": "territory",
        "set_warehouse": "set_warehouse",
    },
    territory_field="territory",
    owner_field="created_by_emp",
    default_order="transaction_date desc",
    sortable_fields=["name", "transaction_date", "customer_name"],
    tabs={
        "draft": {"docstatus": 0},
        "submitted": {"docstatus": 1},
    },
)


@frappe.whitelist()
def secondary_sales_order_list():
    """Paginated, territory-scoped list of channel partner orders."""
    return paginated_list(LIST_CONFIG)


@frappe.whitelist()
def secondary_sales_order(name: str):
    """One channel partner order, with a grand total the doctype itself
    doesn't compute (its controller does nothing - see module docstring)."""
    doc = frappe.get_doc("Secondary Sales Order", name)
    doc.check_permission("read")
    data = doc.as_dict()
    data["grand_total"] = flt(sum(flt(row.amount) for row in doc.items), 2)
    return data


@frappe.whitelist()
def cp_warehouse_list():
    """Channel partner warehouses a rep may book stock from. CP Warehouse
    carries no customer/territory link of its own to scope by (it's a flat
    { warehouse_name } record - see fmcg_cp's cp_warehouse.json), so this is
    the full list rather than a filtered one."""
    if not frappe.has_permission("Secondary Sales Order", "read"):
        raise frappe.PermissionError
    return frappe.get_all("CP Warehouse", fields=["name", "warehouse_name"], order_by="warehouse_name asc")


# ---------------------------------------------------------------- write path
#
# Same allow-list pattern as api/catalog.py: a client can set item_code/qty/
# uom, never rate or amount - those are recomputed server-side in
# _resolve_context regardless of what's sent. customer_level and
# custom_channel_partner aren't writable at all: this doctype exists
# specifically for Secondary customers, and the channel partner is always
# whichever one that customer's own master record already names.

WRITABLE_FIELDS = {
    "customer",
    "transaction_date",
    "delivery_date",
    "set_warehouse",
    "custom_delivery_term",
    "payment_terms_template",
    "customer_address",
    "shipping_address_name",
    "contact_number",
    # Not "customer_visit" - despite the name, that field (owned by fmcg_cp)
    # is a Link to the legacy "Customer Visit Management" doctype, not this
    # app's own Field Visit - discovered via a real LinkValidationError while
    # building the visit-conversion feature below, never actually reachable
    # from the client until now since nothing had ever sent it. fs_field_visit
    # is field_sales's own field (fixtures/custom_field.json), mirroring the
    # one already on native Sales Order.
    "fs_field_visit",
    "remarks",
}

# quote_custom_rate/quoted_rate are real fields the doctype already has
# (Secondary Sales Order Item) for exactly this: a rep-entered rate for an
# item the pricing engine has no Item Price for at all. They're the one
# rate-shaped thing a client may set - _resolve_context only ever reaches
# for quoted_rate when calculate_rate has nothing to offer (see below), so
# this can't be used to undercut a price that does exist.
WRITABLE_ITEM_FIELDS = {"item_code", "qty", "uom", "quote_custom_rate", "quoted_rate"}


def _apply_payload(doc, payload: dict) -> None:
    for key, value in (payload or {}).items():
        if key in WRITABLE_FIELDS:
            doc.set(key, value)

    if "items" in (payload or {}):
        rows = payload.get("items") or []
        if isinstance(rows, str):
            rows = frappe.parse_json(rows)
        doc.set("items", [])
        for row in rows:
            doc.append("items", {k: v for k, v in (row or {}).items() if k in WRITABLE_ITEM_FIELDS})


def _own_employee() -> str | None:
    return frappe.db.get_value(
        "Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
    )


def _resolve_context(doc, employee: str) -> None:
    """Fields the server decides, never the client: who filed it, which
    territory it counts against, and - since this doctype's own controller
    does nothing - the channel partner, every line's rate/amount, and each
    row's item_template (a mandatory field on Secondary Sales Order Item;
    derived from the item itself rather than trusted from the client)."""
    doc.naming_series = doc.naming_series or "SE-S0-.#####"
    doc.created_by_emp = employee

    doc.territory = scope.resolve_leaf_territory(
        doc.get("territory"), employee=employee, fallback_user=frappe.session.user
    )

    doc.customer_level = "Secondary"
    channel_partner = frappe.db.get_value("Customer", doc.customer, "custom_channel_partner")
    if not channel_partner:
        frappe.throw(
            frappe._(
                "{0} has no Channel Partner set on its own customer record, "
                "so a channel partner order can't be booked for it. Fix this "
                "on the Customer record first."
            ).format(doc.customer)
        )
    doc.custom_channel_partner = channel_partner

    for row in doc.items:
        if not row.item_code:
            continue
        try:
            result = pricing.calculate_rate(
                item_code=row.item_code,
                customer=doc.customer,
                qty=flt(row.qty) or 1,
                warehouse=doc.get("set_warehouse"),
                delivery_term=doc.get("custom_delivery_term"),
                payment_terms_template=doc.get("payment_terms_template"),
                transaction_date=str(doc.get("transaction_date") or frappe.utils.nowdate()),
            )
            row.rate = result["final_rate"]
        except pricing.PriceNotFound:
            # Only reached when the engine has nothing at all to offer - a
            # rep-entered quote never overrides a real price, it only ever
            # fills a genuine gap in one.
            if row.quote_custom_rate and flt(row.quoted_rate):
                row.rate = flt(row.quoted_rate)
            else:
                frappe.throw(
                    frappe._(
                        "{0} has no price on file for {1}. Check \"Quote a custom "
                        "rate\" on that item and enter one, or remove the item."
                    ).format(row.item_code, doc.customer)
                )
        row.amount = flt(row.rate) * flt(row.qty)
        if not row.item_template:
            row.item_template = frappe.db.get_value("Item", row.item_code, "variant_of") or row.item_code


# ---------------------------------------------------------------- from a visit
#
# Mirrors field_sales.api.catalog._prepare_visit_conversion/visit_order_prefill
# exactly, for the other half of the same feature: a Secondary customer's
# visit converts into a Channel Partner order (this doctype) instead of a
# native Sales Order. Read-only - the rep reviews and completes the order on
# the real Channel Partner order form, nothing is created here.

def _prepare_secondary_visit_conversion(visit_name: str) -> dict:
    visit = frappe.get_doc("Field Visit", visit_name)
    visit.check_permission("read")

    if not frappe.has_permission("Secondary Sales Order", "create"):
        raise frappe.PermissionError

    if visit.docstatus != 1:
        frappe.throw(frappe._("Only a submitted visit can be converted into an order."))

    if visit.party_type != "Customer" or not visit.customer:
        frappe.throw(frappe._(
            "This visit has no linked Customer, so it cannot become an order. "
            "Convert the prospect to a Customer first."
        ))

    if visit.order_status == "Without Order":
        frappe.throw(frappe._("This visit was recorded as not producing an order."))

    customer_level, channel_partner, cp_name = frappe.db.get_value(
        "Customer", visit.customer, ["customer_level", "custom_channel_partner", "cp_name"]
    )
    if customer_level != "Secondary":
        frappe.throw(frappe._(
            "{0} is not a Secondary customer, so this isn't a channel partner "
            "order - book it as a regular Sales Order instead."
        ).format(visit.customer))
    if not channel_partner:
        frappe.throw(frappe._(
            "{0} has no Channel Partner set on its own customer record, so a "
            "channel partner order can't be booked for it."
        ).format(visit.customer))

    existing = frappe.db.exists(
        "Secondary Sales Order", {"fs_field_visit": visit.name, "docstatus": ["!=", 2]}
    )
    if existing:
        frappe.throw(frappe._(
            "Visit {0} has already been converted to Channel Partner order {1}."
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

    delivery_date = add_days(nowdate(), 7)
    priced_rows, unpriced_codes = [], []
    for row in visit.get("pitched_items") or []:
        if not row.item_code:
            continue
        try:
            result = pricing.calculate_rate(
                item_code=row.item_code, customer=visit.customer, qty=flt(row.qty) or 1,
            )
            priced_rows.append({
                "item_code": row.item_code,
                "item_name": row.item_name or row.item_code,
                "qty": flt(row.qty) or 1,
                "uom": row.uom or None,
                "rate": result["final_rate"],
            })
        except pricing.PriceNotFound:
            unpriced_codes.append(row.item_code)

    if not priced_rows:
        frappe.throw(frappe._(
            "This visit has no pitched items with a resolvable price, so "
            "there is nothing to start an order from."
        ))

    remarks = (
        f"Converted from Field Visit {visit.name}. Quantities below are "
        f"copied from what was pitched during the visit - review and adjust "
        f"before submitting. Rates are recalculated by the server, not "
        f"carried over from the pitch."
    )
    if unpriced_codes:
        remarks += " Left off (no price available): " + ", ".join(unpriced_codes) + "."

    return {
        "visit": visit,
        "employee": employee,
        "delivery_date": delivery_date,
        "priced_rows": priced_rows,
        "remarks": remarks,
        "channel_partner": channel_partner,
        "cp_name": cp_name,
    }


@frappe.whitelist()
def secondary_visit_order_prefill(visit_name: str):
    """Everything the Channel Partner order form needs to start a draft
    from this visit, without creating anything yet."""
    prepared = _prepare_secondary_visit_conversion(visit_name)
    visit = prepared["visit"]
    return {
        "customer": visit.customer,
        "custom_channel_partner": prepared["channel_partner"],
        "cp_name": prepared["cp_name"],
        "contact_number": visit.get("contact_number") or None,
        "delivery_date": prepared["delivery_date"],
        "remarks": prepared["remarks"],
        "fs_field_visit": visit.name,
        "items": prepared["priced_rows"],
    }


@frappe.whitelist(methods=["POST"])
def create_secondary_sales_order(**payload):
    """Start a draft channel partner order. The rep is always the signed-in
    user's own employee; the channel partner and every line's rate are
    derived from the customer, never taken from the client."""
    if not frappe.has_permission("Secondary Sales Order", "create"):
        raise frappe.PermissionError

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    employee = _own_employee()
    if not employee:
        frappe.throw(
            frappe._(
                "Your user account is not linked to an active Employee, so a "
                "channel partner order cannot be filed against you. Ask an "
                "administrator to set the User ID on your Employee record."
            )
        )

    if not (payload or {}).get("customer"):
        frappe.throw(frappe._("Select the customer this order is for."))

    doc = frappe.new_doc("Secondary Sales Order")
    _apply_payload(doc, payload)
    _resolve_context(doc, employee)
    doc.insert(ignore_permissions=True)

    return {"name": doc.name, "docstatus": doc.docstatus, "grand_total": flt(sum(flt(r.amount) for r in doc.items), 2)}


@frappe.whitelist(methods=["POST"])
def update_secondary_sales_order(name: str, **payload):
    """Edit a draft channel partner order. Re-derives the same server-owned
    context as create, so editing the customer cannot silently strand a
    stale channel partner or rate from the previous customer."""
    doc = frappe.get_doc("Secondary Sales Order", name)
    doc.check_permission("write")

    if doc.docstatus != 0:
        frappe.throw(frappe._("Only a draft order can be edited."))

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    employee = _own_employee()
    _apply_payload(doc, payload)
    if employee:
        _resolve_context(doc, employee)
    doc.save(ignore_permissions=True)

    return {"name": doc.name, "docstatus": doc.docstatus, "grand_total": flt(sum(flt(r.amount) for r in doc.items), 2)}


@frappe.whitelist(methods=["POST"])
def submit_secondary_sales_order(name: str):
    """Submit a reviewed channel partner order."""
    doc = frappe.get_doc("Secondary Sales Order", name)
    doc.check_permission("submit")
    doc.submit()
    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist(methods=["POST"])
def cancel_secondary_sales_order(name: str):
    """Cancel a submitted channel partner order."""
    doc = frappe.get_doc("Secondary Sales Order", name)
    doc.check_permission("cancel")
    doc.cancel()
    return {"name": doc.name, "docstatus": doc.docstatus}
