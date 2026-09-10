# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Visit expense claims for the field client.

A rep files travel/visit expenses against a Journey Plan using ERPNext's own
**Expense Claim** doctype (from the `hrms` app) rather than a bespoke
field_sales doctype - there is no reason to reinvent an expense-claim
workflow HR already owns, approves, and reports on. The only thing missing
was a way back to the Journey Plan it was filed for (``fs_journey_plan``,
a Custom Field fixture, mirroring how ``fs_field_visit`` already links a
Sales Order back to the visit it came from) and a Sales Executive App grant
on the doctype (a Custom DocPerm fixture - Expense Claim ships permission
for the standard "Employee" role, not for this app's own role, and that
standard grant has no submit right either).

The Journey Plan side deliberately has no stored link back to the claim -
see journey_plan_expense_status()'s own docstring for why a plain Link
field there turned out to be a real problem, not just an unused shortcut.
"""

import frappe

from field_sales.api.listing import ListConfig, paginated_list

EXPENSE_ITEM_FIELDS = {"expense_type", "expense_date", "amount", "description"}

LIST_CONFIG = ListConfig(
    doctype="Expense Claim",
    fields=[
        "name",
        "posting_date",
        "employee",
        "employee_name",
        "total_claimed_amount",
        "grand_total",
        "status",
        "approval_status",
        "fs_journey_plan",
        "docstatus",
    ],
    search_fields=["name", "employee_name"],
    filter_fields={
        "status": "status",
        "approval_status": "approval_status",
        "fs_journey_plan": "fs_journey_plan",
    },
    territory_field=None,
    owner_field="employee",
    default_order="posting_date desc",
    sortable_fields=["name", "posting_date", "grand_total"],
    tabs={
        "draft": {"docstatus": 0},
        "submitted": {"docstatus": 1},
    },
)


def _own_employee() -> str | None:
    return frappe.db.get_value(
        "Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
    )


@frappe.whitelist()
def visit_expense_claim_list():
    """Paginated list of the caller's own visit expense claims."""
    return paginated_list(LIST_CONFIG)


@frappe.whitelist()
def visit_expense_claim(name: str):
    doc = frappe.get_doc("Expense Claim", name)
    doc.check_permission("read")
    return doc.as_dict()


@frappe.whitelist()
def expense_claim_type_list():
    """Master list a rep picks from - a fixed, small list HR maintains, not
    something a rep can add to."""
    return frappe.get_all("Expense Claim Type", fields=["name", "description"], order_by="name asc")


@frappe.whitelist(methods=["POST"])
def create_visit_expense_claim(journey_plan: str, **payload):
    """File a visit expense claim against a Journey Plan. Employee and
    company are always derived server-side from the signed-in user, never
    taken from the client - same rule as create_journey_plan/create_visit."""
    if not frappe.has_permission("Expense Claim", "create"):
        raise frappe.PermissionError

    if isinstance(payload.get("payload"), str):
        payload = frappe.parse_json(payload["payload"])

    employee = _own_employee()
    if not employee:
        frappe.throw(
            frappe._(
                "Your user account is not linked to an active Employee, so an "
                "expense claim cannot be filed against you. Ask an administrator "
                "to set the User ID on your Employee record."
            )
        )

    plan = frappe.get_doc("Journey Plan", journey_plan)
    plan.check_permission("read")
    if plan.sales_person != employee:
        frappe.throw(
            frappe._("You can only file an expense claim against your own journey plan."),
            exc=frappe.PermissionError,
        )
    if plan.docstatus != 1:
        frappe.throw(frappe._("Only an approved journey plan can have an expense claim filed against it."))

    rows = (payload or {}).get("expenses") or []
    if isinstance(rows, str):
        rows = frappe.parse_json(rows)
    if not rows:
        frappe.throw(frappe._("Add at least one expense."))

    doc = frappe.new_doc("Expense Claim")
    doc.employee = employee
    doc.company = frappe.db.get_value("Employee", employee, "company")
    doc.fs_journey_plan = plan.name
    for row in rows:
        doc.append("expenses", {k: v for k, v in (row or {}).items() if k in EXPENSE_ITEM_FIELDS})
    doc.insert()

    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist(methods=["POST"])
def submit_visit_expense_claim(name: str):
    """Submit a filed visit expense claim - only possible once an Expense
    Approver has already set approval_status to Approved or Rejected
    (Expense Claim's own on_submit refuses while it is still Draft, the
    HRMS-standard "get approved first, then submit" order). A rep files
    the claim as a draft (create_visit_expense_claim never auto-submits);
    this is a separate, later step, not something to chain onto create."""
    doc = frappe.get_doc("Expense Claim", name)
    doc.check_permission("submit")
    doc.submit()
    return {"name": doc.name, "docstatus": doc.docstatus, "status": doc.status}


def journey_plan_expense_status(journey_plan: str) -> dict:
    """The most recent expense claim filed against this Journey Plan (if
    any), and a plain-language status derived live from its real
    docstatus/approval_status. Computed on read rather than stored on the
    plan itself - a stored Link field pointing at the claim would make
    Journey Plan a real back-reference to it, and Frappe refuses to cancel
    or delete an Expense Claim that anything still links to (confirmed by a
    failing test: cancelling a claim a Journey Plan pointed back at was
    refused with a LinkExistsError). Expense Claim's own fs_journey_plan
    field already points the other way - that's the only stored link this
    feature needs."""
    claim = frappe.db.get_value(
        "Expense Claim",
        {"fs_journey_plan": journey_plan},
        ["name", "docstatus", "approval_status"],
        order_by="creation desc",
        as_dict=True,
    )
    if not claim:
        return {"expense_claim": None, "expense_status": None}

    if claim.docstatus == 2:
        status = "Cancelled"
    elif claim.approval_status == "Rejected":
        status = "Rejected"
    elif claim.approval_status == "Approved":
        status = "Approved"
    else:
        status = "Filed"

    return {"expense_claim": claim.name, "expense_status": status}
