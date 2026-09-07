# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Product Demo endpoints.

Replaces api/trial_plan.py and api/trial_target.py - about 400 lines of
string-built SQL between them.
"""

import frappe

from field_sales.api.listing import ListConfig, paginated_list
from field_sales.field_sales.doctype.demo_evaluation.demo_evaluation import summarise

DEMO_CONFIG = ListConfig(
    doctype="Product Demo",
    fields=[
        "name",
        "demo_date",
        "demo_time",
        "demo_location",
        "party_type",
        "customer",
        "customer_name",
        "prospect_name",
        "outlet_name",
        "contact_person",
        "contact_number",
        "conducted_by",
        "specialist",
        "sales_person",
        "sales_person_name",
        "territory",
        "field_visit",
        "status",
        "duration",
        "workflow_state",
        "docstatus",
    ],
    search_fields=["name", "customer_name", "prospect_name", "outlet_name"],
    filter_fields={
        "status": "status",
        "demo_location": "demo_location",
        "conducted_by": "conducted_by",
        "party_type": "party_type",
        "customer": "customer",
        "territory": "territory",
        "demo_date": "demo_date",
        "field_visit": "field_visit",
    },
    territory_field="territory",
    owner_field="sales_person",
    default_order="demo_date desc",
    sortable_fields=["name", "demo_date", "customer_name", "status"],
    tabs={
        "draft": {"docstatus": 0},
        "submitted": {"docstatus": 1},
        "pending": {"status": "Pending"},
        "approved": {"status": "Approved"},
        "rejected": {"status": "Rejected"},
        "completed": {"status": "Completed"},
    },
)

EVALUATION_CONFIG = ListConfig(
    doctype="Demo Evaluation",
    fields=["name", "product_demo", "item_code", "segment", "evaluated_on",
            "outcome", "order_received", "next_expected_order_date"],
    search_fields=["name", "product_demo", "item_code"],
    filter_fields={
        "product_demo": "product_demo",
        "item_code": "item_code",
        "outcome": "outcome",
        "order_received": "order_received",
    },
    # an evaluation is reached through its demo, which is already scoped
    territory_field=None,
    owner_field=None,
    default_order="evaluated_on desc",
    sortable_fields=["name", "evaluated_on", "item_code", "outcome"],
)


@frappe.whitelist()
def demo_list():
    return paginated_list(DEMO_CONFIG)


@frappe.whitelist()
def demo(name: str):
    doc = frappe.get_doc("Product Demo", name)
    doc.check_permission("read")
    data = doc.as_dict()
    data["summary"] = summarise(name)
    return data


@frappe.whitelist()
def evaluation_list():
    return paginated_list(EVALUATION_CONFIG)


@frappe.whitelist()
def demo_parameters():
    """The scorecard template a rep fills in."""
    return frappe.get_all(
        "Demo Parameter",
        filters={"disabled": 0},
        fields=["name", "parameter_name", "value_type", "unit", "requires_remarks"],
        order_by="parameter_name asc",
    )


# ---------------------------------------------------------------- write path
#
# Same allow-list pattern as api/field_visit.py. The scorecard's own defect
# is closed in the controller (DemoEvaluation.validate_lines, in
# doctype/demo_evaluation/demo_evaluation.py), which decides value_type for
# every row itself by looking it up from the row's Demo Parameter - it never
# trusts a value_type sent alongside a rating or a measurement. That is why
# "value_type" does not appear anywhere in the allow-lists below: a client
# cannot make its own row look like a different kind of parameter by naming
# one, because nothing here ever copies that field onto the document at all.

DEMO_WRITABLE_FIELDS = {
    "party_type",
    "customer",
    "prospect_name",
    "outlet_name",
    "contact_person",
    "contact_number",
    "location",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "pincode",
    "demo_date",
    "demo_time",
    "demo_location",
    "conducted_by",
    "specialist",
    "field_visit",
    "remarks",
    "started_on",
    "completed_on",
}

DEMO_WRITABLE_ITEM_FIELDS = {
    "item_code",
    "qty",
    "uom",
    "segment",
    "batch_no",
    "batch_size",
    "no_of_batches",
    "current_dosage",
    "dosage_uom",
    "competitor",
    "competitor_item",
    "monthly_consumption",
    "switch_reason",
    "competitor_remarks",
}

# Never "value_type" - see the note above.
EVALUATION_WRITABLE_FIELDS = {
    "segment",
    "evaluated_on",
    "outcome",
    "order_received",
    "no_order_reason",
    "next_expected_order_date",
    "remarks",
}

EVALUATION_WRITABLE_LINE_FIELDS = {
    "parameter",
    "rating",
    "value",
    "remarks",
}


def _apply_demo_payload(doc, payload: dict) -> None:
    for key, value in (payload or {}).items():
        if key in DEMO_WRITABLE_FIELDS:
            doc.set(key, value)

    if "items" in (payload or {}):
        rows = payload.get("items") or []
        if isinstance(rows, str):
            rows = frappe.parse_json(rows)
        doc.set("items", [])
        for row in rows:
            doc.append(
                "items",
                {k: v for k, v in (row or {}).items() if k in DEMO_WRITABLE_ITEM_FIELDS},
            )


def _apply_evaluation_payload(doc, payload: dict) -> None:
    for key, value in (payload or {}).items():
        if key in EVALUATION_WRITABLE_FIELDS:
            doc.set(key, value)

    if "parameters" in (payload or {}):
        rows = payload.get("parameters") or []
        if isinstance(rows, str):
            rows = frappe.parse_json(rows)
        doc.set("parameters", [])
        for row in rows:
            doc.append(
                "parameters",
                {k: v for k, v in (row or {}).items() if k in EVALUATION_WRITABLE_LINE_FIELDS},
            )


def _own_employee() -> str | None:
    return frappe.db.get_value(
        "Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
    )


@frappe.whitelist(methods=["POST"])
def create_demo(**payload):
    """Start a draft Product Demo. The rep is always the signed in user's own
    employee, same as create_visit in api/field_visit.py."""
    if not frappe.has_permission("Product Demo", "create"):
        raise frappe.PermissionError

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    employee = _own_employee()
    if not employee:
        frappe.throw(
            frappe._(
                "Your user account is not linked to an active Employee, so a "
                "demo cannot be filed against you. Ask an administrator to set "
                "the User ID on your Employee record."
            )
        )

    doc = frappe.new_doc("Product Demo")
    _apply_demo_payload(doc, payload)
    doc.sales_person = employee
    doc.insert()

    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist(methods=["POST"])
def update_demo(name: str, **payload):
    """Edit a draft demo."""
    doc = frappe.get_doc("Product Demo", name)
    doc.check_permission("write")

    if doc.docstatus != 0:
        frappe.throw(frappe._("Only a draft demo can be edited."))

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    _apply_demo_payload(doc, payload)
    doc.save()
    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist(methods=["POST"])
def submit_demo(name: str):
    """Submit a completed demo."""
    doc = frappe.get_doc("Product Demo", name)
    doc.check_permission("submit")
    doc.submit()
    return {"name": doc.name, "docstatus": doc.docstatus, "duration": doc.duration}


def _demo_item_codes(product_demo: str) -> set:
    return set(frappe.get_all(
        "Product Demo Item", filters={"parent": product_demo}, pluck="item_code"
    ))


@frappe.whitelist(methods=["POST"])
def create_evaluation(**payload):
    """Score one item from a demo against the parameter scorecard.

    Type safety - a rating cannot land against a parameter that wants a
    measurement, and vice versa - is enforced by DemoEvaluation.validate_lines
    in the controller, which this endpoint cannot bypass because it never
    copies a client-sent value_type onto any row (see the note above
    EVALUATION_WRITABLE_LINE_FIELDS). This endpoint adds one more check the
    controller does not make on its own: the item being scored has to
    actually be one of the lines on the demo it claims to belong to.
    """
    if not frappe.has_permission("Demo Evaluation", "create"):
        raise frappe.PermissionError

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    product_demo = (payload or {}).get("product_demo")
    item_code = (payload or {}).get("item_code")
    if not (product_demo and item_code):
        frappe.throw(frappe._("Both the demo and the item being scored are required."))

    demo_doc = frappe.get_doc("Product Demo", product_demo)
    demo_doc.check_permission("read")

    if item_code not in _demo_item_codes(product_demo):
        frappe.throw(
            frappe._("{0} was not one of the items demoed on {1}.").format(
                item_code, product_demo
            )
        )

    doc = frappe.new_doc("Demo Evaluation")
    doc.product_demo = product_demo
    doc.item_code = item_code
    _apply_evaluation_payload(doc, payload)
    doc.insert()

    return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def submit_evaluation(name: str):
    """Finalise a scorecard: it must say how the demo turned out before it
    counts as done. Demo Evaluation is not a submittable doctype - this is a
    completeness gate, not a docstatus transition."""
    doc = frappe.get_doc("Demo Evaluation", name)
    doc.check_permission("write")

    if not doc.outcome:
        frappe.throw(frappe._("Say whether the demo was successful before finishing it."))

    doc.save()
    _complete_demo_if_submitted(doc)
    return {"name": doc.name, "outcome": doc.outcome}


def _complete_demo_if_submitted(evaluation) -> None:
    """"Trial can be marked Completed after result entry" - filing a
    scorecard IS the result entry the spec means, so once one lands the
    parent Product Demo should move to Completed on its own, server-side,
    rather than needing a second client call.

    Gated on the demo actually being submitted (docstatus 1): create_evaluation
    does not itself require the demo it scores to be submitted, but jumping a
    still-draft demo straight to "Completed" would let it skip being
    submitted at all - the same shortcut approve_onboarding in
    customer_onboarding.py is careful to close off for Customer Onboarding.
    Also a no-op once the demo is already Completed, so filing more than one
    evaluation against multi-item demo does not re-trigger anything.
    """
    if not evaluation.product_demo:
        return
    demo_doc = frappe.get_doc("Product Demo", evaluation.product_demo)
    if demo_doc.docstatus != 1 or demo_doc.status == "Completed":
        return
    demo_doc.db_set("status", "Completed")
