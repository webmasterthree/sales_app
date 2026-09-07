# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Field Visit endpoints for the client.

The list is a thin declaration over the shared, parameterised helper in
`listing.py`. The equivalent in the app this replaces was ~120 lines of SQL
assembled by string formatting, with the territory filter pasted in as text.
"""

import frappe

from field_sales import geo, uploads
from field_sales.api.listing import ListConfig, paginated_list

LIST_CONFIG = ListConfig(
    doctype="Field Visit",
    fields=[
        "name",
        "party_type",
        "visit_type",
        "channel_partner",
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
        "shop_photo",
    ],
    search_fields=["name", "customer_name", "prospect_name", "outlet_name", "contact_number"],
    filter_fields={
        "party_type": "party_type",
        "visit_type": "visit_type",
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
def reason_list():
    """Active 'Without Order' reasons, for the visit form's picker."""
    return frappe.get_all(
        "Field Reason",
        filters={"applies_to": "Visit", "disabled": 0},
        fields=["name", "reason"],
        order_by="reason asc",
    )


@frappe.whitelist()
def segment_list():
    """Segment options for the pitched-items picker - the real doctype
    items are tagged with (Item.segment -> Segment Mapping -> Segment),
    not Application Segment, which nothing in the catalogue actually uses."""
    return frappe.get_all("Segment", fields=["name"], order_by="name asc")


@frappe.whitelist()
def competitor_list(search_text: str | None = None, limit: int = 20):
    """Competitor options, for the pitched-items picker. The master has no
    size guardrail of its own - competitor rows accumulate across brands and
    regions - so this is searchable rather than returning every row."""
    filters = {}
    if search_text:
        filters["name"] = ["like", f"%{search_text}%"]
    try:
        page_size = int(limit)
    except (TypeError, ValueError):
        page_size = 20
    return frappe.get_all(
        "Competitor", filters=filters, fields=["name"],
        order_by="name asc", limit_page_length=page_size or 20,
    )


@frappe.whitelist()
def uom_list():
    """UOM options, for the consumption entry picker."""
    return frappe.get_all("UOM", fields=["name"], order_by="name asc")


@frappe.whitelist(methods=["POST"])
def set_outlet_location(address: str, latitude: float, longitude: float):
    """A rep drops a pin on the map to correct/set exactly where an outlet
    is - the same fs_latitude/fs_longitude fields geo.anchor_address writes
    automatically from a first check-in, but set explicitly here rather
    than waiting on that to happen by accident.

    Reps have no general write permission on Address (shared master data
    used well beyond this app), the same way the automatic anchor-on-first-
    check-in has none either - see geo.anchor_address, called unconditionally
    from an already-permission-gated check_in. Read permission is the
    equivalent gate here: if a rep can already see this address (every
    visit's customer lookup returns it), recording where its pin actually
    sits is a correction to data they're already trusted to view, not a new
    grant.
    """
    if not frappe.has_permission("Address", "read", doc=address):
        raise frappe.PermissionError
    if not geo.is_valid_position(latitude, longitude):
        frappe.throw(frappe._("That is not a usable map position."))
    geo.anchor_address(address, latitude, longitude)
    return {"address": address, "latitude": frappe.utils.flt(latitude), "longitude": frappe.utils.flt(longitude)}


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
    "visit_type",
    "customer",
    "prospect_name",
    "outlet_name",
    "channel_partner",
    "contact_person",
    "contact_number",
    "visit_date",
    "visit_time",
    "location",
    "address_line1",
    "address_line2",
    "district",
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
    "has_trial_plan",
}

WRITABLE_TABLES = {
    "pitched_items": {"item_code", "qty", "uom", "segment", "competitor", "remarks"},
    "consumption": {"product_name", "monthly_qty", "uom", "segment", "grade"},
    "trial_items": {"item_code", "qty", "uom", "segment", "remarks"},
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


def sync_trial_plans(visit) -> None:
    """Mirrors mohan_impex's CustomerVisitManagement.trial_plan(): checking
    "this visit included a trial" and listing items on it materialises one
    Field Trial Plan per item, linked back to the visit via `field_visit`.
    Unchecking it, or removing an item, removes the matching *draft* trial -
    a trial someone has already submitted or acted on is never touched here,
    the same way the legacy version only deleted its single linked Trial
    Plan while it was still being edited alongside the visit.

    Only meaningful for an actual Customer visit - Field Trial Plan.customer
    is a mandatory Link, and a Prospect has no Customer record yet to trial
    anything against.
    """
    if visit.party_type != "Customer" or not visit.customer:
        return

    existing = frappe.get_all(
        "Field Trial Plan",
        filters={"field_visit": visit.name, "docstatus": 0},
        fields=["name", "item_code"],
    )
    existing_by_item = {row.item_code: row.name for row in existing}

    wanted_items = {row.item_code for row in (visit.trial_items or []) if row.item_code}
    if not visit.has_trial_plan:
        wanted_items = set()

    for item_code, name in existing_by_item.items():
        if item_code not in wanted_items:
            frappe.delete_doc("Field Trial Plan", name, ignore_permissions=True)

    for item_code in wanted_items:
        if item_code in existing_by_item:
            continue
        trial = frappe.new_doc("Field Trial Plan")
        trial.update({
            "customer": visit.customer,
            "item_code": item_code,
            "delivery_date": visit.visit_date,
            "field_visit": visit.name,
            "sales_person": visit.sales_person,
            "territory": visit.territory,
            "remarks": frappe._("Auto-created from visit {0}.").format(visit.name),
        })
        trial.insert(ignore_permissions=True)


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
    sync_trial_plans(doc)

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
    sync_trial_plans(doc)
    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist(methods=["POST"])
def submit_visit(name: str):
    """Submit a completed visit."""
    doc = frappe.get_doc("Field Visit", name)
    doc.check_permission("submit")
    doc.submit()
    return {"name": doc.name, "docstatus": doc.docstatus, "duration": doc.duration}
