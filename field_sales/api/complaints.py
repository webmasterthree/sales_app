# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Complaints and claims.

These are native `Issue` records with a few optional field-sales fields, which
is what the client build did too and one of the better decisions in it.
Replaces `api/complaints.py`.
"""

import frappe
from frappe.utils import nowdate

from field_sales import uploads
from field_sales.api.listing import ListConfig, paginated_list

COMPLAINT_CONFIG = ListConfig(
    doctype="Issue",
    fields=[
        "name",
        "subject",
        "customer",
        "status",
        "priority",
        "opening_date",
        "fs_territory",
        "fs_sales_person",
        "fs_claim_type",
        "fs_field_visit",
        "fs_sales_invoice",
        "fs_resolved_on",
        "fs_photo",
    ],
    search_fields=["name", "subject", "customer"],
    filter_fields={
        "status": "status",
        "priority": "priority",
        "customer": "customer",
        "claim_type": "fs_claim_type",
        "territory": "fs_territory",
        "field_visit": "fs_field_visit",
    },
    territory_field="fs_territory",
    owner_field="fs_sales_person",
    default_order="opening_date desc",
    sortable_fields=["name", "subject", "opening_date", "status", "priority"],
    tabs={
        # Issue's own statuses, named the same way as every other module
        "open": {"status": ["in", ["Open", "Replied", "Paused"]]},
        "resolved": {"status": ["in", ["Resolved", "Closed"]]},
    },
)

# Only these may come from the client.
WRITABLE = {"subject", "description", "customer", "priority",
            "fs_claim_type", "fs_field_visit", "fs_sales_invoice", "fs_photo"}


@frappe.whitelist()
def complaint_list():
    return paginated_list(COMPLAINT_CONFIG)


@frappe.whitelist()
def complaint(name: str):
    doc = frappe.get_doc("Issue", name)
    doc.check_permission("read")
    return doc.as_dict()


@frappe.whitelist(methods=["POST"])
def raise_complaint(**payload):
    """Log a complaint from the field."""
    if not frappe.has_permission("Issue", "create"):
        raise frappe.PermissionError

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    if not (payload.get("subject") or "").strip():
        frappe.throw(frappe._("Give the complaint a subject."))

    doc = frappe.new_doc("Issue")
    for key, value in payload.items():
        if key in WRITABLE:
            doc.set(key, value)

    employee = frappe.db.get_value(
        "Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
    )
    doc.fs_sales_person = employee
    doc.fs_territory = _territory_for(doc, employee)
    doc.opening_date = nowdate()

    # Issue also carries a legacy mandatory `claim_type` (Transit / Quality)
    # from before this app added its own richer `fs_claim_type` (Transit /
    # Quality / Service / Other). Nothing here ever populated the legacy
    # field, so every call used to fail insert() with a MandatoryError
    # regardless of what the caller sent. Map onto it where the value is
    # compatible, and fall back to a safe default rather than leaving it
    # empty.
    if not doc.get("claim_type"):
        doc.claim_type = doc.fs_claim_type if doc.fs_claim_type in ("Transit", "Quality") else "Quality"

    doc.insert()

    uploads.link_uploaded_file(doc.fs_photo, "Issue", doc.name, "fs_photo")

    return {"name": doc.name, "status": doc.status}


def _territory_for(doc, employee):
    """Prefer the customer's territory, fall back to the rep's own."""
    if doc.customer:
        territory = frappe.db.get_value("Customer", doc.customer, "territory")
        if territory:
            return territory
    if employee:
        return frappe.db.get_value("Employee", employee, "area")
    return None


@frappe.whitelist(methods=["POST"])
def resolve_complaint(name: str, resolution: str | None = None):
    """Close a complaint out."""
    doc = frappe.get_doc("Issue", name)
    doc.check_permission("write")

    doc.status = "Resolved"
    doc.fs_resolved_on = nowdate()
    if resolution:
        doc.resolution_details = resolution
    doc.save()
    return {"name": doc.name, "status": doc.status, "resolved_on": doc.fs_resolved_on}
