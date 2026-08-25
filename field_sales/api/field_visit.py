# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Field Visit endpoints for the client.

The list is a thin declaration over the shared, parameterised helper in
`listing.py`. The equivalent in the app this replaces was ~120 lines of SQL
assembled by string formatting, with the territory filter pasted in as text.
"""

import frappe

from field_sales import uploads
from field_sales.api.listing import ListConfig, paginated_list

LIST_CONFIG = ListConfig(
    doctype="Field Visit",
    fields=[
        "name",
        "party_type",
        "customer",
        "customer_name",
        "prospect_name",
        "outlet_name",
        "contact_number",
        "visit_date",
        "visit_time",
        "city",
        "territory",
        "order_status",
        "deal_confidence",
        "sales_person",
        "sales_person_name",
        "duration",
        "onboarding_status",
        "workflow_state",
        "docstatus",
    ],
    search_fields=["name", "customer_name", "prospect_name", "outlet_name", "contact_number"],
    filter_fields={
        "party_type": "party_type",
        "order_status": "order_status",
        "onboarding_status": "onboarding_status",
        "customer": "customer",
        "territory": "territory",
        "visit_date": "visit_date",
        "demo_requested": "demo_requested",
    },
    territory_field="territory",
    owner_field="sales_person",
    default_order="visit_date desc",
    sortable_fields=["name", "visit_date", "customer_name", "order_status", "duration"],
    tabs={
        # the app's two tabs, named consistently rather than per-module
        "draft": {"docstatus": 0},
        "submitted": {"docstatus": 1},
    },
)


@frappe.whitelist()
def visit_list():
    """Paginated, territory-scoped list of visits."""
    return paginated_list(LIST_CONFIG)


@frappe.whitelist()
def visit(name: str):
    """One visit, with its child tables."""
    doc = frappe.get_doc("Field Visit", name)
    doc.check_permission("read")
    return doc.as_dict()


# ---------------------------------------------------------------- write path

# Only these may be set by a client. Everything else - who filed it, which
# territory it counts against, the timestamps, the duration, the geofence
# verdict - is decided by the server. The app this replaces copied the whole
# payload onto the document, which is how a client came to control its own
# order rates.
WRITABLE_FIELDS = {
    "party_type",
    "customer",
    "prospect_name",
    "outlet_name",
    "contact_person",
    "contact_number",
    "visit_date",
    "visit_time",
    "location",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "pincode",
    "shop_photo",
    "order_status",
    "deal_confidence",
    "reason",
    "remarks",
    "demo_requested",
    "demo_location",
    "demo_conducted_by",
    "demo_remarks",
    "customer_update_requested",
    "lead",
    "opportunity",
}

WRITABLE_TABLES = {
    "pitched_items": {"item_code", "qty", "uom", "segment", "competitor", "remarks"},
    "consumption": {"product_name", "monthly_qty", "uom", "segment", "grade"},
}


def _apply_payload(doc, payload: dict) -> None:
    """Copy only the declared fields onto the document."""
    for key, value in (payload or {}).items():
        if key in WRITABLE_FIELDS:
            doc.set(key, value)

    for table, allowed in WRITABLE_TABLES.items():
        if table not in (payload or {}):
            continue
        rows = payload.get(table) or []
        if isinstance(rows, str):
            rows = frappe.parse_json(rows)
        doc.set(table, [])
        for row in rows:
            doc.append(table, {k: v for k, v in (row or {}).items() if k in allowed})


def _own_employee() -> str | None:
    return frappe.db.get_value(
        "Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
    )


@frappe.whitelist(methods=["POST"])
def create_visit(**payload):
    """Start a visit. The rep is always the signed-in user's own employee."""
    if not frappe.has_permission("Field Visit", "create"):
        raise frappe.PermissionError

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    employee = _own_employee()
    if not employee:
        frappe.throw(
            frappe._(
                "Your user account is not linked to an active Employee, so a visit "
                "cannot be filed against you. Ask an administrator to set the User ID "
                "on your Employee record."
            )
        )

    doc = frappe.new_doc("Field Visit")
    _apply_payload(doc, payload)
    doc.sales_person = employee
    doc.insert()

    uploads.link_uploaded_file(doc.shop_photo, "Field Visit", doc.name, "shop_photo")

    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist(methods=["POST"])
def update_visit(name: str, **payload):
    """Edit a draft visit."""
    doc = frappe.get_doc("Field Visit", name)
    doc.check_permission("write")

    if doc.docstatus != 0:
        frappe.throw(frappe._("Only a draft visit can be edited."))

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    _apply_payload(doc, payload)
    doc.save()
    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist(methods=["POST"])
def submit_visit(name: str):
    """Submit a completed visit."""
    doc = frappe.get_doc("Field Visit", name)
    doc.check_permission("submit")
    doc.submit()
    return {"name": doc.name, "docstatus": doc.docstatus, "duration": doc.duration}
