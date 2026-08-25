# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Customer Onboarding endpoints.

Replaces `api/kyc.py`. The original's list ran a raw SQL join against
`Customer`/`Contact Number`/`Dynamic Link` filtered by `workflow_state` -
onboarding is now its own doctype, so it is a normal list.
"""

import frappe

from field_sales import uploads
from field_sales.api.listing import ListConfig, paginated_list

ONBOARDING_CONFIG = ListConfig(
    doctype="Customer Onboarding",
    fields=[
        "name",
        "customer_name",
        "business_type",
        "contact_number",
        "territory",
        "sales_person",
        "sales_person_name",
        "request_date",
        "status",
        "customer",
        "field_visit",
        "workflow_state",
        "docstatus",
    ],
    search_fields=["name", "customer_name", "contact_number"],
    filter_fields={
        "status": "status",
        "business_type": "business_type",
        "territory": "territory",
        "field_visit": "field_visit",
    },
    territory_field="territory",
    owner_field="sales_person",
    default_order="request_date desc",
    sortable_fields=["name", "customer_name", "request_date", "status"],
    tabs={
        "draft": {"docstatus": 0},
        "pending": {"docstatus": 1, "status": "Pending"},
        "approved": {"status": "Approved"},
        "rejected": {"status": "Rejected"},
    },
)


@frappe.whitelist()
def onboarding_list():
    return paginated_list(ONBOARDING_CONFIG)


@frappe.whitelist()
def onboarding(name: str):
    doc = frappe.get_doc("Customer Onboarding", name)
    doc.check_permission("read")
    return doc.as_dict()


# Only these may come from the client. Status, customer, decided_on and
# decision_remarks are set exclusively by approve_onboarding/reject_onboarding.
WRITABLE = {
    "customer_name", "business_type", "gst_category", "gstin", "pan",
    "market_segment", "customer_group", "location", "contact_person",
    "contact_number", "territory", "field_visit", "proposed_credit",
    "credit_days", "credit_limit",
}
WRITABLE_TABLES = {"documents": {"document_type", "attachment", "number", "remarks"}}


def _own_employee() -> str | None:
    return frappe.db.get_value(
        "Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
    )


def _apply_payload(doc, payload: dict) -> None:
    for key, value in (payload or {}).items():
        if key in WRITABLE:
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


@frappe.whitelist(methods=["POST"])
def create_onboarding(**payload):
    if not frappe.has_permission("Customer Onboarding", "create"):
        raise frappe.PermissionError

    employee = _own_employee()
    if not employee:
        frappe.throw(
            frappe._(
                "Your user account is not linked to an active Employee, so an "
                "onboarding request cannot be filed against you."
            )
        )

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    doc = frappe.new_doc("Customer Onboarding")
    _apply_payload(doc, payload)
    doc.sales_person = employee
    doc.insert()

    for row in doc.get("documents") or []:
        uploads.link_uploaded_file(row.attachment, "Customer Onboarding", doc.name, "attachment")

    return {"name": doc.name, "status": doc.status}


@frappe.whitelist(methods=["POST"])
def update_onboarding(name: str, **payload):
    doc = frappe.get_doc("Customer Onboarding", name)
    doc.check_permission("write")
    if doc.docstatus != 0:
        frappe.throw(frappe._("Only a draft onboarding request can be edited."))

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    _apply_payload(doc, payload)
    doc.save()
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist(methods=["POST"])
def submit_onboarding(name: str):
    doc = frappe.get_doc("Customer Onboarding", name)
    doc.check_permission("submit")
    doc.submit()
    return {"name": doc.name, "docstatus": doc.docstatus, "status": doc.status}
