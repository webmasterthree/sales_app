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
        "customer_level",
        "cp_name",
        "disabled",
    ],
    search_fields=["name", "customer_name", "mobile_no"],
    filter_fields={
        "customer_group": "customer_group",
        "territory": "territory",
        "disabled": "disabled",
        "customer_level": "customer_level",
        "custom_channel_partner": "custom_channel_partner",
    },
    territory_field="territory",
    # Customer has no "raised by" employee, so the mine/team toggle is not
    # offered here rather than being faked.
    owner_field=None,
    default_order="customer_name asc",
    sortable_fields=["name", "customer_name", "customer_group", "territory"],
    # The org's own Customer master already carries this distinction
    # (customer_level - see Customer-custom_channel_partner's depends_on) -
    # surfaced here as tabs, matching how the legacy my_customer list let a
    # rep switch between their Primary (distributor) and Secondary (outlet)
    # customers rather than showing one undifferentiated list.
    tabs={
        "primary": {"customer_level": "Primary"},
        "secondary": {"customer_level": "Secondary"},
    },
)


@frappe.whitelist()
def customer_list():
    return paginated_list(CUSTOMER_CONFIG)


# Customers flagged is_dl=1 (distributor-level) are the only ones the org's
# own Customer master allows as a Secondary customer's channel partner - see
# Customer-custom_channel_partner's link_filters (fmcg_cp's customer.json).
# A Prospect visit has no Customer record yet to derive this from, so its
# channel-partner picker still needs a real, correctly-scoped list to search
# rather than the generic (and, for this purpose, wrong) customer_list.
DISTRIBUTOR_CONFIG = ListConfig(
    doctype="Customer",
    fields=["name", "customer_name", "territory"],
    search_fields=["name", "customer_name"],
    filter_fields={"territory": "territory"},
    territory_field="territory",
    owner_field=None,
    default_order="customer_name asc",
    sortable_fields=["name", "customer_name"],
    base_filters={"is_dl": 1, "disabled": 0},
)


@frappe.whitelist()
def distributor_list():
    """Distributor-level customers, for picking a channel partner."""
    return paginated_list(DISTRIBUTOR_CONFIG)


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
                "address_line2", "district", "city", "state", "pincode",
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


@frappe.whitelist()
def invoice_items(invoice: str):
    """Line items on a submitted invoice, to prefill a complaint's claimed
    items - a rep filing a complaint against a specific invoice should start
    from what was actually billed on it, not re-pick items from the whole
    catalogue a second time.

    Gated on the invoice's own Customer, not Sales Invoice itself - same
    convention customer_ledger already uses just above. A field rep's role
    has no real document-level read permission on Sales Invoice (only
    customer_ledger's own frappe.get_all can see it, since get_all bypasses
    permission checks by design) - has_permission("Sales Invoice", ...)
    would refuse every real rep outright.
    """
    customer = frappe.db.get_value("Sales Invoice", invoice, "customer")
    if not customer or not frappe.has_permission("Customer", "read", doc=customer):
        raise frappe.PermissionError
    return frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": invoice},
        fields=["item_code", "item_name", "qty", "uom", "batch_no", "amount"],
        order_by="idx asc",
    )


@frappe.whitelist()
def customer_change_requests(customer: str):
    """Past change requests raised for this customer, newest first - the
    Change Log a rep sees before deciding whether to raise another one."""
    if not frappe.has_permission("Customer", "read", doc=customer):
        raise frappe.PermissionError
    return frappe.get_all(
        "Customer Change Request",
        filters={"customer": customer},
        fields=["name", "requested_change", "status", "resolution_notes", "creation"],
        order_by="creation desc",
    )


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
