# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Creates the in-app Notification Log entries field_sales' own business
events raise (visit completed, order submitted/cancelled, ...). Every insert
here is automatically relayed as an FCM push too - see api/push.py's hook on
Notification Log's own after_insert.

Deciding who to notify follows one rule, mirrored from HRMS's own
notify_approval_status/notify_approver split (hrms/mixins/pwa_notifications.py):
the person who performed the action doesn't need telling about their own
action. So a rep finishing their own record notifies their manager, while
someone else (a manager, Administrator, ...) changing the rep's record
notifies the rep instead.
"""

import frappe
from frappe import _


def notify_sales_order_submitted(doc, method=None):
    _notify_sales_order(doc, _("Order {0} for {1} was submitted").format(doc.name, doc.customer_name or doc.customer))


def notify_sales_order_cancelled(doc, method=None):
    _notify_sales_order(doc, _("Order {0} for {1} was cancelled").format(doc.name, doc.customer_name or doc.customer))


def _notify_sales_order(doc, message):
    # created_by_emp is a custom field field_sales grafts onto Sales Order
    # (see api/catalog.py's _resolve_order_context) - guard the same way
    # catalog.py does, since a deployment without it has no rep to notify.
    if not doc.meta.has_field("created_by_emp") or not doc.get("created_by_emp"):
        return
    # See notify_employee_event's own docstring: submit_order/cancel_order
    # run the actual submit/cancel under an elevated Administrator session
    # (_as_a_privileged_user), so the real acting user is stashed on the doc
    # beforehand rather than trusted from frappe.session.user here.
    actor = doc.flags.get("notify_actor") if doc.flags else None
    notify_employee_event(doc.created_by_emp, doc.doctype, doc.name, message, actor=actor)


def notify_expense_claim_created(doc, method=None):
    # fs_journey_plan (a Custom Field fixture - see api/expense_claim.py)
    # only exists on a claim filed through this app's own visit-expense
    # flow; a plain HR-filed Expense Claim has no fs_journey_plan and no
    # rep waiting on a field_sales notification about it.
    if not doc.get("fs_journey_plan") or not doc.get("employee"):
        return
    notify_employee_event(
        doc.employee, doc.doctype, doc.name,
        _("Expense claim {0} is waiting on your approval").format(doc.name),
    )


def notify_expense_claim_decided(doc, method=None):
    if not doc.get("fs_journey_plan") or not doc.get("employee"):
        return
    if not doc.has_value_changed("approval_status") or doc.approval_status not in ("Approved", "Rejected"):
        return
    notify_employee_event(
        doc.employee, doc.doctype, doc.name,
        _("Expense claim {0} was {1}").format(doc.name, doc.approval_status.lower()),
    )


def notify_employee_event(employee: str, doctype: str, name: str, message: str, actor: str | None = None) -> None:
    """employee: the Employee this document belongs to (the rep). Notifies
    that rep's reporting manager if the rep is the one acting right now,
    otherwise notifies the rep about whatever the other party just did.

    `actor` defaults to frappe.session.user, but some write paths (e.g.
    catalog.py's submit_order, which briefly elevates to Administrator via
    _as_a_privileged_user to submit on the rep's behalf) run the actual
    document event under a different session user than the person who really
    triggered it - those callers should pass the real actor explicitly.
    """
    if not employee:
        return

    actor = actor or frappe.session.user
    rep_user = frappe.db.get_value("Employee", employee, "user_id")
    if not rep_user:
        return

    if actor == rep_user:
        reports_to = frappe.db.get_value("Employee", employee, "reports_to")
        to_user = reports_to and frappe.db.get_value("Employee", reports_to, "user_id")
    else:
        to_user = rep_user

    if not to_user or to_user == actor:
        return

    try:
        notification = frappe.new_doc("Notification Log")
        notification.for_user = to_user
        notification.from_user = actor
        notification.subject = message
        notification.type = "Alert"
        notification.document_type = doctype
        notification.document_name = name
        notification.insert(ignore_permissions=True)
    except Exception:
        # A notification is a side effect of the real action - never let a
        # failure here (e.g. a stray validation on Notification Log) block
        # the visit/order update that triggered it.
        frappe.log_error(title="field_sales notify_employee_event", message=frappe.get_traceback())
