# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Sample Request, Collateral Request and Sales Collateral endpoints.

Three modules, three declarations. The equivalents in the app this replaces -
`api/sample.py`, `api/collateral_request.py`, `api/marketing_collateral.py` -
came to roughly 350 lines of SQL built by string formatting, each repeating
the same pagination, search, tab and territory logic slightly differently.
"""

import frappe
from frappe import _

from field_sales import scope
from field_sales.api.listing import ListConfig, paginated_list

# Requests share a shape, so they share a builder.
REQUEST_FIELDS = [
    "name",
    "request_date",
    "required_by",
    "party_type",
    "customer",
    "customer_name",
    "prospect_name",
    "sales_person",
    "sales_person_name",
    "territory",
    "field_visit",
    "status",
    "workflow_state",
    "docstatus",
]

REQUEST_FILTERS = {
    "status": "status",
    "party_type": "party_type",
    "customer": "customer",
    "territory": "territory",
    "request_date": "request_date",
    "field_visit": "field_visit",
}

# Every list in the app used to name this split differently - My Visit /
# Visit Draft, My Orders / Draft Order, Approved / Pending. One vocabulary.
REQUEST_TABS = {
    "draft": {"docstatus": 0},
    "submitted": {"docstatus": 1},
    "pending": {"status": "Pending"},
    "approved": {"status": "Approved"},
    "rejected": {"status": "Rejected"},
}


def request_config(doctype: str) -> ListConfig:
    return ListConfig(
        doctype=doctype,
        fields=REQUEST_FIELDS,
        search_fields=["name", "customer_name", "prospect_name", "sales_person_name"],
        filter_fields=dict(REQUEST_FILTERS),
        territory_field="territory",
        owner_field="sales_person",
        default_order="request_date desc",
        sortable_fields=["name", "request_date", "required_by", "customer_name", "status"],
        tabs=dict(REQUEST_TABS),
    )


SAMPLE_CONFIG = request_config("Sample Request")
COLLATERAL_CONFIG = request_config("Collateral Request")

COLLATERAL_LIBRARY_CONFIG = ListConfig(
    doctype="Sales Collateral",
    fields=["name", "collateral_name", "collateral_type", "segment",
            "thumbnail", "attachment", "description"],
    search_fields=["collateral_name", "description"],
    filter_fields={"collateral_type": "collateral_type", "segment": "segment"},
    # the library is shared across the company, so it is not territory scoped
    territory_field=None,
    owner_field=None,
    default_order="collateral_name asc",
    sortable_fields=["collateral_name", "collateral_type"],
)


@frappe.whitelist()
def sample_request_list():
    return paginated_list(SAMPLE_CONFIG)


@frappe.whitelist()
def collateral_request_list():
    return paginated_list(COLLATERAL_CONFIG)


@frappe.whitelist()
def collateral_library():
    """The published collateral a rep can show or share on a visit."""
    form = frappe._dict(frappe.form_dict or {})
    form["published"] = 1
    config = COLLATERAL_LIBRARY_CONFIG
    config.filter_fields["published"] = "published"
    return paginated_list(config, form=form)


@frappe.whitelist()
def sample_request(name: str):
    doc = frappe.get_doc("Sample Request", name)
    doc.check_permission("read")
    return doc.as_dict()


@frappe.whitelist()
def collateral_request(name: str):
    doc = frappe.get_doc("Collateral Request", name)
    doc.check_permission("read")
    return doc.as_dict()


# ---------------------------------------------------------------- write path
#
# Neither the app this replaces nor the first pass of this rebuild gave a
# rep any way to actually file a Sample Request or a Collateral Request -
# only list/detail existed, even though both doctypes already carry a
# "Sales Executive App" create permission and the Flutter app has a working
# "+" screen for each. Same allow-list pattern as api/field_visit.py and
# api/demo.py: neither Sample Request nor Collateral Request has a
# controller that fills in sales_person/territory itself (unlike Field
# Visit), so this endpoint derives them explicitly, the same way
# api/catalog.py's _resolve_order_context does for Sales Order.

REQUEST_WRITABLE_FIELDS = {
    "party_type",
    "customer",
    "prospect_name",
    "request_date",
    "required_by",
    "field_visit",
    "purpose",
}

SAMPLE_ITEM_FIELDS = {"item_code", "qty", "uom", "remarks"}

# Collateral Request Item links to Sales Collateral (the published library
# behind collateral_library() above), not to a generic Item - a rep is
# requesting a specific piece of published marketing material, not a
# stock-keeping unit.
COLLATERAL_ITEM_FIELDS = {"collateral", "description", "qty", "remarks"}


def _apply_request_payload(doc, payload: dict, item_fields: set) -> None:
    for key, value in (payload or {}).items():
        if key in REQUEST_WRITABLE_FIELDS:
            doc.set(key, value)

    if "items" in (payload or {}):
        rows = payload.get("items") or []
        if isinstance(rows, str):
            rows = frappe.parse_json(rows)
        doc.set("items", [])
        for row in rows:
            doc.append(
                "items",
                {k: v for k, v in (row or {}).items() if k in item_fields},
            )


def _own_employee() -> str | None:
    return frappe.db.get_value(
        "Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
    )


def _resolve_request_context(doc, employee: str, throw_label: str) -> None:
    """Fields the server decides: who filed it, and which territory it
    counts against - never taken from the client."""
    doc.sales_person = employee
    doc.territory = scope.resolve_leaf_territory(
        doc.get("territory"), employee=employee, fallback_user=frappe.session.user
    )
    if not doc.territory:
        frappe.throw(_("Give a territory for this {0}.").format(throw_label))


@frappe.whitelist(methods=["POST"])
def create_sample_request(**payload):
    """Start a Sample Request. The rep is always the signed-in user's own
    employee; the territory is derived, never taken from the client."""
    if not frappe.has_permission("Sample Request", "create"):
        raise frappe.PermissionError

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    employee = _own_employee()
    if not employee:
        frappe.throw(
            _(
                "Your user account is not linked to an active Employee, so a "
                "sample request cannot be filed against you. Ask an administrator "
                "to set the User ID on your Employee record."
            )
        )

    if not (payload or {}).get("items"):
        frappe.throw(_("Add at least one item to the sample request."))

    doc = frappe.new_doc("Sample Request")
    doc.party_type = (payload or {}).get("party_type") or "Customer"
    _apply_request_payload(doc, payload, SAMPLE_ITEM_FIELDS)
    _resolve_request_context(doc, employee, "sample request")
    doc.insert()

    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist(methods=["POST"])
def create_collateral_request(**payload):
    """Start a Collateral Request. Same rep/territory derivation as
    create_sample_request above."""
    if not frappe.has_permission("Collateral Request", "create"):
        raise frappe.PermissionError

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    employee = _own_employee()
    if not employee:
        frappe.throw(
            _(
                "Your user account is not linked to an active Employee, so a "
                "collateral request cannot be filed against you. Ask an "
                "administrator to set the User ID on your Employee record."
            )
        )

    if not (payload or {}).get("items"):
        frappe.throw(_("Add at least one collateral item to the request."))

    doc = frappe.new_doc("Collateral Request")
    doc.party_type = (payload or {}).get("party_type") or "Customer"
    _apply_request_payload(doc, payload, COLLATERAL_ITEM_FIELDS)
    _resolve_request_context(doc, employee, "collateral request")
    doc.insert()

    return {"name": doc.name, "docstatus": doc.docstatus}
