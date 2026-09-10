# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Trial Plan endpoints for the client.

Same shape as api/field_visit.py: a thin, permission-checked list over
listing.py, and a write path that only ever copies a fixed allowlist of
fields onto the document. Who filed the trial and which territory it counts
against are always decided by the server, never by the client.
"""

import frappe

from field_sales.api.listing import ListConfig, paginated_list

LIST_CONFIG = ListConfig(
    doctype="Field Trial Plan",
    fields=[
        "name",
        "visit_type",
        "customer",
        "customer_name",
        "channel_partner",
        "item_code",
        "item_name",
        "delivery_date",
        "sales_person",
        "sales_person_name",
        "territory",
        "field_visit",
        "sample_distributed",
        "feedback_collected",
        "follow_up_order",
        "status",
        "docstatus",
    ],
    search_fields=["name", "customer_name", "item_name"],
    filter_fields={
        "visit_type": "visit_type",
        "customer": "customer",
        "item_code": "item_code",
        "territory": "territory",
        "delivery_date": "delivery_date",
        "status": "status",
        "field_visit": "field_visit",
    },
    territory_field="territory",
    owner_field="sales_person",
    default_order="delivery_date desc",
    sortable_fields=["name", "delivery_date", "customer_name", "status"],
    tabs={
        "draft": {"docstatus": 0},
        "submitted": {"docstatus": 1},
        "scheduled": {"status": "Scheduled"},
        "completed": {"status": "Completed"},
    },
)


@frappe.whitelist()
def trial_plan_list():
    """Paginated, territory-scoped list of trial plans."""
    return paginated_list(LIST_CONFIG)


@frappe.whitelist()
def trial_plan(name: str):
    """One trial plan."""
    doc = frappe.get_doc("Field Trial Plan", name)
    doc.check_permission("read")
    return doc.as_dict()


# ---------------------------------------------------------------- write path

WRITABLE_FIELDS = {
    "visit_type",
    "customer",
    "channel_partner",
    "contact_person",
    "contact_number",
    "item_code",
    "delivery_date",
    "territory",
    "field_visit",
    "remarks",
}

# The attendance checklist is the one thing still writable after submit -
# these are things that happen *because of* the trial, not part of planning
# it, so locking them to the draft-only WRITABLE_FIELDS above would make a
# submitted (i.e. actually happening) trial impossible to ever mark attended.
ATTENDANCE_WRITABLE_FIELDS = {
    "sample_distributed",
    "feedback_collected",
    "follow_up_order",
}


def _apply_payload(doc, payload: dict) -> None:
    for key, value in (payload or {}).items():
        if key in WRITABLE_FIELDS:
            doc.set(key, value)


def _own_employee() -> str | None:
    return frappe.db.get_value(
        "Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
    )


@frappe.whitelist(methods=["POST"])
def create_trial_plan(**payload):
    """Start a draft trial plan. The rep is always the signed-in user's own employee."""
    if not frappe.has_permission("Field Trial Plan", "create"):
        raise frappe.PermissionError

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    employee = _own_employee()
    if not employee:
        frappe.throw(
            frappe._(
                "Your user account is not linked to an active Employee, so a "
                "trial plan cannot be filed against you. Ask an administrator "
                "to set the User ID on your Employee record."
            )
        )

    doc = frappe.new_doc("Field Trial Plan")
    _apply_payload(doc, payload)
    doc.sales_person = employee
    doc.insert()

    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist(methods=["POST"])
def update_trial_plan(name: str, **payload):
    """Edit a draft (not yet submitted) trial plan."""
    doc = frappe.get_doc("Field Trial Plan", name)
    doc.check_permission("write")

    if doc.docstatus != 0:
        frappe.throw(frappe._("Only a draft trial plan can be edited."))

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    _apply_payload(doc, payload)
    doc.save()
    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist(methods=["POST"])
def submit_trial_plan(name: str):
    """Submit a planned trial."""
    doc = frappe.get_doc("Field Trial Plan", name)
    doc.check_permission("submit")
    doc.submit()
    return {"name": doc.name, "docstatus": doc.docstatus, "status": doc.status}


@frappe.whitelist(methods=["POST"])
def update_attendance(name: str, **payload):
    """Record what actually happened after the trial was submitted - sample
    handed over, feedback collected, a follow-up order linked. Allowed on a
    submitted trial (unlike update_trial_plan's draft-only fields), since
    these facts only exist once the trial has actually happened."""
    doc = frappe.get_doc("Field Trial Plan", name)
    doc.check_permission("write")

    if doc.docstatus != 1:
        frappe.throw(frappe._("Only a submitted trial plan has attendance to record."))

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    if payload.get("follow_up_order"):
        order = frappe.get_doc("Sales Order", payload["follow_up_order"])
        if order.customer != doc.customer:
            frappe.throw(frappe._("That order was not booked for this trial's customer."))

    for key, value in (payload or {}).items():
        if key in ATTENDANCE_WRITABLE_FIELDS:
            doc.set(key, value)

    doc.save()
    return {
        "name": doc.name,
        "status": doc.status,
        "sample_distributed": doc.sample_distributed,
        "feedback_collected": doc.feedback_collected,
        "follow_up_order": doc.follow_up_order,
    }
