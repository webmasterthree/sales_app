# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Customer Onboarding endpoints.

Replaces `api/kyc.py`. The original's list ran a raw SQL join against
`Customer`/`Contact Number`/`Dynamic Link` filtered by `workflow_state` -
onboarding is now its own doctype, so it is a normal list.
"""

import frappe
from frappe.utils import getdate, nowdate

from field_sales import scope, uploads
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
def onboarding_funnel_report() -> dict:
    """The approval funnel for Customer Onboarding requests in the caller's
    territory - how many are still pending, how many were approved or
    rejected, and how long a decision actually took. onboarding_list's own
    status tabs only ever show one bucket at a time; this is the rollup
    across all of them, plus the one thing no list view surfaces at all:
    days from request to decision.

    Doubles as a real replacement for Reports' disabled "New Wins" tile -
    an onboarding reaching Approved is exactly a new customer won, and
    unlike a fabricated counter this reads the real decided_on/status
    fields approve_onboarding already stamps, rather than inventing new
    tracking.
    """
    user = frappe.session.user
    filters = {}
    filters.update(scope.territory_filter(user, "territory"))

    rows = frappe.get_all(
        "Customer Onboarding",
        filters=filters,
        fields=["name", "customer_name", "territory", "docstatus", "status",
                "request_date", "decided_on"],
    )

    draft = [r for r in rows if r.docstatus == 0]
    pending = [r for r in rows if r.docstatus == 1 and r.status == "Pending"]
    approved = [r for r in rows if r.status == "Approved"]
    rejected = [r for r in rows if r.status == "Rejected"]

    decision_days = [
        (getdate(r.decided_on) - getdate(r.request_date)).days
        for r in approved + rejected
        if r.request_date and r.decided_on
    ]
    avg_decision_days = round(sum(decision_days) / len(decision_days), 1) if decision_days else None

    today = getdate(nowdate())
    pending_rows = []
    for r in pending:
        waiting_days = (today - getdate(r.request_date)).days if r.request_date else None
        pending_rows.append({
            "name": r.name,
            "customer_name": r.customer_name,
            "territory": r.territory,
            "request_date": r.request_date,
            "waiting_days": waiting_days,
        })
    # Longest-waiting request first - the one most overdue for a decision.
    pending_rows.sort(key=lambda r: -(r["waiting_days"] or 0))

    return {
        "draft_count": len(draft),
        "pending_count": len(pending),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "avg_decision_days": avg_decision_days,
        "pending": pending_rows,
    }


@frappe.whitelist()
def onboarding(name: str):
    doc = frappe.get_doc("Customer Onboarding", name)
    doc.check_permission("read")
    return doc.as_dict()


# Only these may come from the client. Status, customer, decided_on and
# decision_remarks are set exclusively by approve_onboarding/reject_onboarding.
WRITABLE = {
    "customer_name", "business_type", "gst_category", "gstin", "pan",
    "market_segment", "customer_group", "location",
    "address_line1", "address_line2", "city", "district", "state", "pincode",
    "contact_person", "contact_number", "territory", "field_visit",
    "proposed_credit", "credit_days", "credit_limit",
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
