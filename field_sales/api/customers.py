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
from frappe.utils import cint, flt, getdate, nowdate

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
    filter_fields={},
    # Not scoped by the generic territory_field mechanism - a distributor's
    # own `territory` records where *it* is registered, which routinely
    # differs from where the outlets it actually serves are (a distributor
    # can be based in one city and supply Secondary customers all over the
    # state). Scoping on that field would hide a rep's own real channel
    # partner just because head office sits outside their patch. See
    # distributor_list below for the scoping that's actually correct here.
    territory_field=None,
    owner_field=None,
    default_order="customer_name asc",
    sortable_fields=["name", "customer_name"],
    # is_dl alone isn't a safe distributor test: it's meant to mark a
    # Primary customer as a channel partner, but bad data has left it set
    # on several Secondary customers too (their own channel partner's own
    # flag, copied onto them by mistake). Requiring customer_level=Primary
    # as well keeps a mis-flagged outlet from ever showing up as a channel
    # partner option, regardless of what is_dl says on its own.
    base_filters={"is_dl": 1, "customer_level": "Primary", "disabled": 0},
)


@frappe.whitelist()
def distributor_list():
    """Distributor-level customers, for picking a channel partner.

    Scoped to distributors that actually have a Secondary customer in the
    caller's own territory - not to the distributor's own `territory`
    field (see DISTRIBUTOR_CONFIG's comment for why that's the wrong
    dimension). A rep who can already see a Secondary customer needs to be
    able to find that customer's real channel partner, wherever the
    distributor itself is nominally registered.
    """
    extra_filters = None
    if not scope.has_unrestricted_scope():
        territories = scope.effective_territories()
        reachable: list[str] = []
        if territories:
            reachable = list(
                {
                    name
                    for name in frappe.get_all(
                        "Customer",
                        filters={
                            "customer_level": "Secondary",
                            "territory": ["in", territories],
                        },
                        pluck="custom_channel_partner",
                    )
                    if name
                }
            )
        # An empty list here must mean "no reachable distributor", not "no
        # filter" - frappe.get_all treats `["in", []]` as "match nothing",
        # which is exactly the fail-closed behaviour a scoped user with no
        # reachable distributors needs.
        extra_filters = {"name": ["in", reachable]}
    return paginated_list(DISTRIBUTOR_CONFIG, extra_filters=extra_filters)


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
def mode_of_payment_list() -> list:
    """Every Mode of Payment on file, for the collection form's picker -
    a small, bounded master list, same convention as a plain frappe.get_all
    with no search needed (see the sweep that added search everywhere it was
    actually needed - this one was correctly left alone)."""
    return frappe.get_all(
        "Mode of Payment", filters={"enabled": 1}, fields=["name", "type"], order_by="name"
    )


def _mode_of_payment_account(mode_of_payment: str, company: str) -> str:
    """The account a collected payment actually lands in - ERPNext lets a
    Mode of Payment carry a per-company default (Mode of Payment Account),
    and only falls back to the company's own default cash/bank account when
    no such row exists, exactly like the desk Payment Entry form does."""
    account = frappe.db.get_value(
        "Mode of Payment Account",
        {"parent": mode_of_payment, "company": company},
        "default_account",
    )
    if account:
        return account

    mop_type = frappe.db.get_value("Mode of Payment", mode_of_payment, "type")
    company_doc = frappe.get_cached_doc("Company", company)
    account = company_doc.default_cash_account if mop_type == "Cash" else company_doc.default_bank_account
    if not account:
        frappe.throw(
            frappe._(
                "No default account is configured for {0}. Ask an administrator to set one up."
            ).format(mode_of_payment)
        )
    return account


def _build_payment_entry(
    customer: str,
    employee: str,
    mode_of_payment: str,
    reference_no: str | None,
    group_amounts: dict,
    found: dict,
):
    """One submitted Payment Entry for a single reference number (or none,
    e.g. Cash) - allocated across whichever invoices in ``group_amounts``
    share that reference, splitting across Payment Schedule terms within an
    invoice where payment-term-based allocation is enabled."""
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    names = list(group_amounts.keys())
    total_amount = flt(sum(group_amounts.values()), 2)

    pe = get_payment_entry("Sales Invoice", names[0], party_amount=total_amount)
    pe.mode_of_payment = mode_of_payment
    pe.paid_to = _mode_of_payment_account(mode_of_payment, pe.company)
    pe.reference_no = reference_no or f"Field collection - {employee}"
    pe.reference_date = nowdate()
    pe.paid_amount = total_amount
    pe.received_amount = total_amount
    if pe.meta.has_field("created_by_emp"):
        pe.created_by_emp = employee

    # Payment Entry has no field of its own for "who recorded this and
    # through what channel" - reusing reference_no for that would break
    # the moment a rep enters a real cheque/UTR number. A fixed marker in
    # remarks is what collections_history() below greps for to tell a
    # field collection apart from a desk-entered Payment Entry, without
    # adding a new custom field just to carry one flag.
    marker = f"Recorded via field_sales app by {employee}."
    pe.remarks = f"{pe.remarks}\n{marker}" if pe.remarks else marker

    schedules_by_invoice: dict[str, list] = {}
    for row in frappe.get_all(
        "Payment Schedule",
        filters={"parent": ["in", names], "outstanding": [">", 0]},
        fields=["parent", "payment_term", "due_date", "payment_amount", "outstanding"],
        order_by="parent, due_date asc",
    ):
        schedules_by_invoice.setdefault(row.parent, []).append(row)

    pe.set("references", [])
    for name in names:
        inv = found[name]
        invoice_remaining = group_amounts[name]
        schedule = schedules_by_invoice.get(name)
        if not schedule:
            # No payment-term split on this invoice - one reference row
            # against the whole thing.
            pe.append(
                "references",
                {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": name,
                    "due_date": inv.due_date,
                    "total_amount": inv.outstanding_amount,
                    "outstanding_amount": inv.outstanding_amount,
                    "allocated_amount": invoice_remaining,
                },
            )
            continue

        # This invoice has "Payment Term based allocation" enabled -
        # ERPNext requires a payment_term on every reference row in that
        # case, and refuses an allocation that doesn't respect each term's
        # own outstanding. Walk the schedule oldest-due-first, bounded to
        # what the rep entered for this invoice.
        for term in schedule:
            if invoice_remaining <= 0.01:
                break
            alloc = min(flt(term.outstanding), invoice_remaining)
            pe.append(
                "references",
                {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": name,
                    "payment_term": term.payment_term,
                    "due_date": term.due_date,
                    "total_amount": term.payment_amount,
                    "outstanding_amount": term.outstanding,
                    "allocated_amount": alloc,
                },
            )
            invoice_remaining -= alloc

    pe.insert()
    pe.submit()
    return pe


@frappe.whitelist()
def record_collection(
    customer: str,
    invoice_amounts: str | dict,
    mode_of_payment: str,
    invoice_references: str | dict | None = None,
    reference_no: str | None = None,
) -> dict:
    """Record a payment collected from a customer in the field.

    Creates real, submitted Payment Entries - the same document type the
    desk side and every ledger/report already reads - rather than a
    parallel "collection" record only this app would understand.

    ``invoice_amounts`` is ``{invoice_name: amount_to_allocate}`` - the rep
    picks which invoices and how much against each (a partial amount on one
    invoice, the full outstanding on another), rather than this function
    guessing an oldest-due-first split from a single total.

    ``invoice_references`` is an optional ``{invoice_name: reference_no}`` -
    a rep collecting against several invoices in one visit may be handed a
    different cheque or UTR for each. A Payment Entry only ever carries one
    reference number, so invoices are grouped by their reference (falling
    back to the plain ``reference_no`` argument, then to nothing for Cash)
    and one Payment Entry is created per group - never one document with a
    reference number that only applies to some of its lines.
    """
    if not frappe.has_permission("Customer", "read", doc=customer):
        raise frappe.PermissionError

    if not scope.has_unrestricted_scope():
        customer_territory = frappe.db.get_value("Customer", customer, "territory")
        if customer_territory not in scope.effective_territories():
            frappe.throw(frappe._("{0} is outside your territory.").format(customer))

    if isinstance(invoice_amounts, str):
        invoice_amounts = frappe.parse_json(invoice_amounts)
    invoice_amounts = {name: flt(amt) for name, amt in (invoice_amounts or {}).items() if flt(amt) > 0}
    if not invoice_amounts:
        frappe.throw(frappe._("Select at least one invoice and enter an amount."))

    if isinstance(invoice_references, str):
        invoice_references = frappe.parse_json(invoice_references)
    invoice_references = invoice_references or {}

    mop_type = frappe.db.get_value("Mode of Payment", mode_of_payment, "type")

    employee = frappe.db.get_value(
        "Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
    )
    if not employee:
        frappe.throw(frappe._("No active Employee record is linked to your account."))

    names = list(invoice_amounts.keys())
    outstanding = frappe.get_all(
        "Sales Invoice",
        filters={"customer": customer, "name": ["in", names], "docstatus": 1, "outstanding_amount": [">", 0]},
        fields=["name", "outstanding_amount", "due_date"],
    )
    found = {inv.name: inv for inv in outstanding}
    missing = [name for name in names if name not in found]
    if missing:
        frappe.throw(
            frappe._("These invoices are not outstanding for {0}: {1}").format(customer, ", ".join(missing))
        )

    for name, amt in invoice_amounts.items():
        if amt > flt(found[name].outstanding_amount) + 0.01:
            frappe.throw(
                frappe._("{0} cannot exceed its outstanding amount of {1}.").format(
                    name, flt(found[name].outstanding_amount, 2)
                )
            )

    groups: dict[str, dict] = {}
    for name in names:
        ref = (invoice_references.get(name) or reference_no or "").strip()
        groups.setdefault(ref, {})[name] = invoice_amounts[name]

    if mop_type != "Cash" and not any(ref for ref in groups):
        frappe.throw(frappe._("Enter a reference number for {0}.").format(mode_of_payment))

    # get_payment_entry (and Payment Entry's own validate()) read the
    # account's balance via erpnext.accounts.utils.get_balance_on, which
    # checks read permission on Account unless this flag is set - correct
    # for a desk user browsing the chart of accounts, wrong for a field rep
    # who is only ever posting against a company-derived, system-picked
    # account they never see or choose themselves.
    frappe.flags.ignore_account_permission = True
    try:
        entries = [
            _build_payment_entry(customer, employee, mode_of_payment, ref or None, group_amounts, found)
            for ref, group_amounts in groups.items()
        ]
    finally:
        frappe.flags.ignore_account_permission = False

    return {
        "payment_entries": [pe.name for pe in entries],
        "amount": flt(sum(pe.paid_amount for pe in entries), 2),
        "customer": customer,
    }


@frappe.whitelist()
def collections_history(limit: int = 50) -> list:
    """Recent payments recorded through record_collection above - not every
    Payment Entry against a Customer, which would also surface anything the
    accounts team enters directly on the desk. Scoped to the caller's own
    territory, same as collections_report()."""
    limit = cint(limit) or 50

    filters = {
        "payment_type": "Receive",
        "party_type": "Customer",
        "docstatus": 1,
        "remarks": ["like", "%Recorded via field_sales app%"],
    }

    if not scope.has_unrestricted_scope():
        territories = scope.effective_territories()
        if not territories:
            return []
        customers = frappe.get_all("Customer", filters={"territory": ["in", territories]}, pluck="name")
        if not customers:
            return []
        filters["party"] = ["in", customers]

    rows = frappe.get_all(
        "Payment Entry",
        filters=filters,
        fields=[
            "name",
            "party as customer",
            "party_name as customer_name",
            "paid_amount",
            "mode_of_payment",
            "posting_date",
            "reference_no",
            "owner",
        ],
        order_by="posting_date desc, creation desc",
        limit_page_length=limit,
    )

    owners = {r.owner for r in rows}
    employees = (
        frappe.get_all("Employee", filters={"user_id": ["in", list(owners)]}, fields=["user_id", "employee_name"])
        if owners
        else []
    )
    name_by_user = {e.user_id: e.employee_name for e in employees}
    for r in rows:
        r["collected_by"] = name_by_user.get(r.owner, r.owner)
        r["paid_amount"] = flt(r.paid_amount, 2)

    return rows


@frappe.whitelist()
def collection_detail(name: str) -> dict:
    """One collection's full detail - which invoices it was applied
    against and how much of each - for tapping into a row on the
    collections_history() list."""
    pe = frappe.get_doc("Payment Entry", name)

    if (
        pe.payment_type != "Receive"
        or pe.party_type != "Customer"
        or "Recorded via field_sales app" not in (pe.remarks or "")
    ):
        frappe.throw(frappe._("Collection not found."))

    if not scope.has_unrestricted_scope():
        customer_territory = frappe.db.get_value("Customer", pe.party, "territory")
        if customer_territory not in scope.effective_territories():
            raise frappe.PermissionError

    collected_by = frappe.db.get_value("Employee", {"user_id": pe.owner}, "employee_name") or pe.owner

    alloc_by_invoice: dict[str, float] = {}
    for row in pe.references:
        if row.reference_doctype != "Sales Invoice":
            continue
        alloc_by_invoice[row.reference_name] = alloc_by_invoice.get(row.reference_name, 0) + flt(row.allocated_amount)

    current_outstanding = {
        inv.name: flt(inv.outstanding_amount)
        for inv in frappe.get_all(
            "Sales Invoice",
            filters={"name": ["in", list(alloc_by_invoice.keys())]},
            fields=["name", "outstanding_amount"],
        )
    } if alloc_by_invoice else {}

    references = [
        {
            "invoice": invoice,
            "allocated_amount": flt(amount, 2),
            "outstanding_amount": current_outstanding.get(invoice, 0),
        }
        for invoice, amount in alloc_by_invoice.items()
    ]

    return {
        "name": pe.name,
        "customer": pe.party,
        "customer_name": pe.party_name,
        "paid_amount": flt(pe.paid_amount, 2),
        "mode_of_payment": pe.mode_of_payment,
        "posting_date": str(pe.posting_date),
        "reference_no": pe.reference_no,
        "collected_by": collected_by,
        "references": references,
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
def coverage_report(min_days: int = 30) -> dict:
    """Customers in the caller's territory, sorted by how long it has been
    since a submitted Field Visit against them - the gap neither Visit
    Report (one day at a time) nor Performance (ranks reps, not customers)
    answers: which of MY customers have I actually not been to see.

    Scoped by the customer's own territory field, same as customer_list -
    unlike distributor_list, there is no "wrong dimension" trap here, since
    the question is genuinely about customers registered in my patch, not
    about a distributor's downstream outlets elsewhere.

    ``min_days`` only changes the overdue count in the summary - every
    scoped customer is still returned (most overdue, or never visited,
    first), so a shorter window never hides anyone from the list itself.
    """
    user = frappe.session.user
    min_days = max(1, cint(min_days) or 30)

    filters = {"disabled": 0}
    filters.update(scope.territory_filter(user, "territory"))
    customers = frappe.get_all(
        "Customer",
        filters=filters,
        fields=["name", "customer_name", "customer_level", "territory"],
    )
    if not customers:
        return {"records": [], "overdue_count": 0, "min_days": min_days, "total_count": 0}

    names = [c.name for c in customers]
    last_visits = {
        r.customer: r.last_visit
        for r in frappe.get_all(
            "Field Visit",
            filters={"customer": ["in", names], "docstatus": 1},
            group_by="customer",
            fields=["customer", "max(visit_date) as last_visit"],
        )
    }

    today = getdate(nowdate())
    records = []
    for c in customers:
        last_visit = last_visits.get(c.name)
        days_since = (today - getdate(last_visit)).days if last_visit else None
        records.append({
            "name": c.name,
            "customer_name": c.customer_name,
            "customer_level": c.customer_level,
            "territory": c.territory,
            "last_visit_date": last_visit,
            "days_since": days_since,
        })

    # Never-visited customers are the biggest gap of all, so they sort
    # first - then longest-overdue first, then alphabetically so ties don't
    # reorder between two otherwise-identical requests.
    records.sort(key=lambda r: (
        0 if r["days_since"] is None else 1,
        -(r["days_since"] or 0),
        r["customer_name"] or "",
    ))

    overdue_count = sum(1 for r in records if r["days_since"] is None or r["days_since"] >= min_days)
    return {
        "records": records,
        "overdue_count": overdue_count,
        "min_days": min_days,
        "total_count": len(records),
    }


@frappe.whitelist()
def collections_report(min_outstanding: float = 0) -> dict:
    """Outstanding balance across every customer in the caller's territory,
    ranked by amount owed - customer_ledger already computes this same
    figure, but only for one customer at a time. This is the rollup a rep
    or manager needs to decide who to chase first, without opening every
    customer's ledger one by one.

    Reads Sales Invoice directly (like customer_ledger does) rather than
    via frappe.get_list, since a field rep's role has no document-level
    read permission on Sales Invoice itself - only the Customer scoping
    check below stands in for that, matching the convention already used
    everywhere else in this module.
    """
    user = frappe.session.user
    min_outstanding = flt(min_outstanding)

    filters = {"disabled": 0}
    filters.update(scope.territory_filter(user, "territory"))
    customers = frappe.get_all(
        "Customer",
        filters=filters,
        fields=["name", "customer_name", "customer_level", "territory"],
    )
    if not customers:
        return {"records": [], "total_outstanding": 0, "total_overdue_count": 0, "total_count": 0}

    names = [c.name for c in customers]
    today = getdate(nowdate())
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"customer": ["in", names], "docstatus": 1, "outstanding_amount": [">", 0]},
        fields=["customer", "outstanding_amount", "due_date"],
    )

    # One pass over every scoped customer's invoices, rather than one query
    # per customer (what a naive port of customer_ledger's own loop would
    # do) - the same batching principle _orders_by_employee already uses
    # in field_sales.api.home.
    by_customer: dict[str, dict] = {}
    for inv in invoices:
        entry = by_customer.setdefault(inv.customer, {"outstanding": 0.0, "invoice_count": 0, "overdue_count": 0})
        entry["outstanding"] += flt(inv.outstanding_amount)
        entry["invoice_count"] += 1
        if inv.due_date and getdate(inv.due_date) < today:
            entry["overdue_count"] += 1

    records = []
    for c in customers:
        totals = by_customer.get(c.name)
        if not totals or totals["outstanding"] < min_outstanding:
            continue
        records.append({
            "name": c.name,
            "customer_name": c.customer_name,
            "customer_level": c.customer_level,
            "territory": c.territory,
            "outstanding": round(totals["outstanding"], 2),
            "invoice_count": totals["invoice_count"],
            "overdue_count": totals["overdue_count"],
        })
    records.sort(key=lambda r: -r["outstanding"])

    return {
        "records": records,
        "total_outstanding": round(sum(r["outstanding"] for r in records), 2),
        "total_overdue_count": sum(r["overdue_count"] for r in records),
        "total_count": len(records),
    }


@frappe.whitelist()
def my_territories():
    """What the signed-in user is scoped to. Used by the client for filters."""
    return {
        "territories": scope.effective_territories(),
        "unrestricted": scope.has_unrestricted_scope(),
    }
