# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Journey Plan endpoints for the client.

Same shape as api/field_visit.py: a thin, permission-checked list over
listing.py, and a write path that only ever copies a fixed allowlist of
fields onto the document. Who filed the plan and which territory it counts
against are always decided by the server, never by the client - see
field_visit.py's WRITABLE_FIELDS docstring for why that matters.
"""

import frappe
from frappe.model.workflow import apply_workflow, get_transitions
from frappe.utils import nowdate

from field_sales import scope
from field_sales.api.listing import ListConfig, paginated_list

LIST_CONFIG = ListConfig(
    doctype="Journey Plan",
    fields=[
        "name",
        "visit_date",
        "nature_of_travel",
        "territory",
        "sales_person",
        "sales_person_name",
        "remarks",
        "workflow_state",
        "docstatus",
    ],
    search_fields=["name", "sales_person_name", "territory"],
    filter_fields={
        "nature_of_travel": "nature_of_travel",
        "territory": "territory",
        "visit_date": "visit_date",
    },
    territory_field="territory",
    owner_field="sales_person",
    default_order="visit_date desc",
    sortable_fields=["name", "visit_date", "sales_person_name"],
    # Driven by workflow_state (the real ASM -> NSM approval chain), not
    # docstatus - a plan sits at docstatus 0 all the way until an NSM's own
    # Approve action submits it, so "approved" here has to mean the real
    # approved state, not merely "submitted". See journey_plan_actions/
    # apply_journey_plan_action below for how a plan actually moves between
    # these states.
    tabs={
        "pending": {"workflow_state": ["in", ["Pending", "ASM Approved"]]},
        "approved": {"workflow_state": "Approved"},
        "rejected": {"workflow_state": "Rejected"},
    },
)


@frappe.whitelist()
def journey_plan_list():
    """Paginated, territory-scoped list of journey plans."""
    return paginated_list(LIST_CONFIG)


@frappe.whitelist()
def journey_plan(name: str):
    """One journey plan, with its trips and its expense claim status (if
    any) - see api/expense_claim.py's journey_plan_expense_status for why
    that's computed live rather than a field on this doctype."""
    from field_sales.api.expense_claim import journey_plan_expense_status

    doc = frappe.get_doc("Journey Plan", name)
    doc.check_permission("read")
    data = doc.as_dict()
    data.update(journey_plan_expense_status(name))
    return data


# ------------------------------------------------------- location cascade
#
# State/District/City are owned by the legacy `mohan_impex` app (this
# rebuild doesn't yet have its own geography master), so this reads that
# app's doctypes rather than field_sales's own. Read-only, no writes -
# safe to depend on for now, but worth revisiting if mohan_impex is ever
# fully retired.


@frappe.whitelist()
def state_list():
    return frappe.get_all("State", fields=["name", "state"], order_by="state asc")


@frappe.whitelist()
def district_list(state: str):
    return frappe.get_all(
        "District", filters={"state": state}, fields=["name", "district"], order_by="district asc"
    )


@frappe.whitelist()
def city_list(district: str):
    return frappe.get_all(
        "City", filters={"district": district}, fields=["name", "city"], order_by="city asc"
    )


# ---------------------------------------------------------------- write path

WRITABLE_FIELDS = {
    "visit_date",
    "nature_of_travel",
    "territory",
    "remarks",
}

WRITABLE_TABLES = {
    "trips": {
        "travel_state_from",
        "travel_from_district",
        "travel_from_city",
        "same_as_from_address",
        "travel_to_state",
        "travel_to_district",
        "travel_to_city",
        "mode_of_travel",
        "primary_customer",
        "secondary_customer",
    },
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
def create_journey_plan(**payload):
    """Start a journey plan. The rep is always the signed-in user's own employee."""
    if not frappe.has_permission("Journey Plan", "create"):
        raise frappe.PermissionError

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    employee = _own_employee()
    if not employee:
        frappe.throw(
            frappe._(
                "Your user account is not linked to an active Employee, so a journey "
                "plan cannot be filed against you. Ask an administrator to set the "
                "User ID on your Employee record."
            )
        )

    doc = frappe.new_doc("Journey Plan")
    _apply_payload(doc, payload)
    doc.sales_person = employee
    doc.insert()

    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist(methods=["POST"])
def update_journey_plan(name: str, **payload):
    """Edit a draft (pending) journey plan."""
    doc = frappe.get_doc("Journey Plan", name)
    doc.check_permission("write")

    if doc.docstatus != 0:
        frappe.throw(frappe._("Only a pending journey plan can be edited."))

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    _apply_payload(doc, payload)
    doc.save()
    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist(methods=["POST"])
def submit_journey_plan(name: str):
    """Submit a journey plan directly, bypassing the ASM -> NSM approval
    chain. Kept for any other caller that still wants the old
    create-then-submit-yourself behaviour; the app's own Detail page now
    goes through apply_journey_plan_action instead, since a plan is only
    meant to reach docstatus 1 via an NSM's own Approve action - see
    journey_plan_actions/apply_journey_plan_action below.

    Real bug this guards against: every plan submitted this way before the
    workflow existed ended up with workflow_state stuck at "Pending" while
    docstatus was already 1 - a mismatch Frappe's own apply_workflow can't
    recover from later (it throws "Illegal Document Status", since nothing
    in its state machine expects a submitted document to still be sitting
    in a draft-mapped state). Setting workflow_state here too keeps this
    path internally consistent with the real workflow, whether or not this
    function is ever actually called again.
    """
    doc = frappe.get_doc("Journey Plan", name)
    doc.check_permission("submit")
    doc.submit()
    if doc.meta.has_field("workflow_state") and doc.workflow_state != "Approved":
        frappe.db.set_value("Journey Plan", doc.name, "workflow_state", "Approved")
        doc.workflow_state = "Approved"
    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist(methods=["POST"])
def cancel_journey_plan(name: str):
    """Cancel an approved journey plan."""
    doc = frappe.get_doc("Journey Plan", name)
    doc.check_permission("cancel")
    doc.cancel()
    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist(methods=["POST"])
def delete_journey_plan(name: str):
    """Delete a pending (draft) journey plan."""
    doc = frappe.get_doc("Journey Plan", name)
    doc.check_permission("delete")
    if doc.docstatus != 0:
        frappe.throw(frappe._("Only a pending journey plan can be deleted."))
    frappe.delete_doc("Journey Plan", name)
    return {"name": name}


# --------------------------------------------------------- ASM -> NSM approval
#
# A real Workflow document (Pending -> ASM Approved -> Approved, with
# Reject and revise-after-Reject branches) drives this - not bespoke code
# here. Only the "Approved" state has doc_status=1, so a plan only ever
# reaches docstatus 1 as a side effect of an NSM's own Approve transition;
# a rep can no longer self-submit their own plan (create_journey_plan
# already never did). frappe.model.workflow already re-validates that the
# signed-in user's role actually permits the requested transition from the
# document's current state - these two endpoints don't duplicate that
# check, they just expose it to the client.


@frappe.whitelist()
def journey_plan_actions(name: str):
    """Which workflow actions (Approve/Reject/...) the signed-in user can
    currently take on this plan, if any - drives which buttons the Detail
    page shows, computed from the real Workflow rather than guessed at
    client-side from role names alone."""
    doc = frappe.get_doc("Journey Plan", name)
    doc.check_permission("read")
    return [{"action": t.action, "next_state": t.next_state} for t in get_transitions(doc)]


@frappe.whitelist(methods=["POST"])
def apply_journey_plan_action(name: str, action: str):
    """Move a Journey Plan through its real approval workflow."""
    doc = frappe.get_doc("Journey Plan", name)
    doc.check_permission("read")
    doc = apply_workflow(doc, action)
    return {"name": doc.name, "docstatus": doc.docstatus, "workflow_state": doc.workflow_state}


# --------------------------------------------------------- visit-vs-plan report
#
# "For this date, which Journey Plans were made, and did the rep actually
# visit the field - where?" There is no stored link between Journey Plan
# and Field Visit (a plan's own Trips are what was *intended*, not a
# reference to what was actually logged), so the two are correlated the
# only way that makes sense without one: same rep, same calendar date. A
# manager sees every plan/visit their own territory scope already covers
# (scope.territory_filter, same rule the leaderboard report uses) - an
# individual rep sees only their own day.

VISIT_REPORT_FIELDS = [
    "name",
    "sales_person",
    "sales_person_name",
    "party_type",
    "customer_name",
    "prospect_name",
    "visit_time",
    "check_in",
    "check_out",
    "check_in_latitude",
    "check_in_longitude",
    "check_out_latitude",
    "check_out_longitude",
    "geofence_status",
    "captured_address",
    "order_status",
]


@frappe.whitelist()
def journey_plan_visit_report(date: str | None = None):
    """Every Journey Plan for the given date (default today) within the
    caller's territory scope, each carrying the Field Visit(s) its own rep
    actually logged that same day - with check-in/out geolocation, so a
    manager can see not just *that* a visit was recorded but *where*."""
    date = date or nowdate()
    user = frappe.session.user

    plan_filters = {"visit_date": date, "docstatus": 1}
    plan_filters.update(scope.territory_filter(user, "territory"))
    plans = frappe.get_all(
        "Journey Plan",
        filters=plan_filters,
        fields=["name", "sales_person", "sales_person_name", "territory", "nature_of_travel"],
        order_by="sales_person_name asc",
    )

    visit_filters = {"visit_date": date, "docstatus": 1}
    visit_filters.update(scope.territory_filter(user, "territory"))
    visits = frappe.get_all("Field Visit", filters=visit_filters, fields=VISIT_REPORT_FIELDS)

    visits_by_employee: dict[str, list] = {}
    for visit in visits:
        visits_by_employee.setdefault(visit.sales_person, []).append(visit)

    for plan in plans:
        plan["visits"] = visits_by_employee.get(plan.sales_person, [])

    # A rep who logged visits with no journey plan filed for the day still
    # matters to a manager checking the day's activity - surfaced as their
    # own group rather than silently dropped.
    planned_employees = {p.sales_person for p in plans}
    unplanned = [
        {
            "name": None,
            "sales_person": emp,
            "sales_person_name": rows[0].get("sales_person_name") or emp,
            "territory": None,
            "nature_of_travel": None,
            "visits": rows,
        }
        for emp, rows in visits_by_employee.items()
        if emp and emp not in planned_employees
    ]

    return plans + unplanned
