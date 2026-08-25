# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Customer endpoints for the field client.

Replaces `api/my_customer.py`, which was the worst offender in the audit -
10 string-formatted SQL sites, 9 of them reachable from user input.

Customers are read-only in the field. A rep who spots a wrong address raises a
`Customer Change Request` rather than editing the record, which is the pattern
the client build had and is worth keeping.
"""

import frappe
from frappe.utils import flt, getdate, nowdate

from field_sales import scope
from field_sales.api.listing import ListConfig, paginated_list

CUSTOMER_CONFIG = ListConfig(
    doctype="Customer",
    fields=[
        "name",
        "customer_name",
        "customer_group",
        "territory",
        "mobile_no",
        "email_id",
        "customer_primary_contact",
        "disabled",
    ],
    search_fields=["name", "customer_name", "mobile_no"],
    filter_fields={
        "customer_group": "customer_group",
        "territory": "territory",
        "disabled": "disabled",
    },
    territory_field="territory",
    # Customer has no "raised by" employee, so the mine/team toggle is not
    # offered here rather than being faked.
    owner_field=None,
    default_order="customer_name asc",
    sortable_fields=["name", "customer_name", "customer_group", "territory"],
)


@frappe.whitelist()
def customer_list():
    return paginated_list(CUSTOMER_CONFIG)


@frappe.whitelist()
def customer(name: str):
    """One customer, with the addresses and contacts a rep needs on a visit."""
    doc = frappe.get_doc("Customer", name)
    doc.check_permission("read")

    data = doc.as_dict()
    data["addresses"] = frappe.get_all(
        "Address",
        filters=[
            ["Dynamic Link", "link_doctype", "=", "Customer"],
            ["Dynamic Link", "link_name", "=", name],
        ],
        fields=["name", "address_title", "address_type", "address_line1",
                "address_line2", "city", "state", "pincode",
                "fs_latitude", "fs_longitude"],
    )
    data["contacts"] = frappe.get_all(
        "Contact",
        filters=[
            ["Dynamic Link", "link_doctype", "=", "Customer"],
            ["Dynamic Link", "link_name", "=", name],
        ],
        fields=["name", "first_name", "last_name", "mobile_no", "email_id"],
    )
    return data


@frappe.whitelist()
def customer_ledger(customer: str, from_date: str | None = None,
                    to_date: str | None = None) -> dict:
    """Outstanding invoices and the running balance.

    The original built this with a date range pasted into SQL::

        date_range = "BETWEEN '{0}' AND '{1}' ".format(
            frappe.form_dict["from_date"], frappe.form_dict["to_date"])
    """
    if not frappe.has_permission("Customer", "read", doc=customer):
        raise frappe.PermissionError

    filters = {"customer": customer, "docstatus": 1}
    if from_date and to_date:
        # dates are validated then passed as values, never as text
        filters["posting_date"] = ["between", [getdate(from_date), getdate(to_date)]]

    invoices = frappe.get_all(
        "Sales Invoice",
        filters=filters,
        fields=["name", "posting_date", "due_date", "grand_total",
                "outstanding_amount", "status"],
        order_by="posting_date desc",
    )

    return {
        "customer": customer,
        "invoices": invoices,
        "total_billed": flt(sum(flt(i.grand_total) for i in invoices), 2),
        "total_outstanding": flt(sum(flt(i.outstanding_amount) for i in invoices), 2),
        "overdue_count": sum(
            1 for i in invoices
            if flt(i.outstanding_amount) > 0 and i.due_date and getdate(i.due_date) < getdate(nowdate())
        ),
    }


@frappe.whitelist(methods=["POST"])
def request_customer_change(customer: str, requested_change: str):
    """A rep flags that a customer record needs correcting."""
    if not frappe.has_permission("Customer", "read", doc=customer):
        raise frappe.PermissionError
    if not (requested_change or "").strip():
        frappe.throw(frappe._("Describe what needs changing."))

    doc = frappe.new_doc("Customer Change Request")
    doc.update({
        "customer": customer,
        "requested_change": requested_change.strip(),
        "requested_by": frappe.db.get_value(
            "Employee", {"user_id": frappe.session.user}, "name"
        ),
        "status": "Pending",
    })
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def my_territories():
    """What the signed-in user is scoped to. Used by the client for filters."""
    return {
        "territories": scope.effective_territories(),
        "unrestricted": scope.has_unrestricted_scope(),
    }
