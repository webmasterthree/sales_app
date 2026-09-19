# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Desk drill-down for the PWA's own Onboarding Funnel report - the app
screen shows bucketed counts; this lists every underlying Customer
Onboarding request so a manager can group/pivot in Desk (by Status,
Territory, ...) rather than only seeing the four totals. Same territory
scoping as field_sales.api.onboarding.onboarding_funnel_report, read
directly here since that function returns bucketed counts rather than the
flat rows a Script Report needs."""

import frappe
from frappe.utils import getdate

from field_sales import scope

COLUMNS = [
    {"label": "Onboarding", "fieldname": "name", "fieldtype": "Link", "options": "Customer Onboarding", "width": 150},
    {"label": "Customer Name", "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
    {"label": "Territory", "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 150},
    {"label": "Status", "fieldname": "status_label", "fieldtype": "Data", "width": 100},
    {"label": "Request Date", "fieldname": "request_date", "fieldtype": "Date", "width": 110},
    {"label": "Decided On", "fieldname": "decided_on", "fieldtype": "Date", "width": 110},
    {"label": "Days to Decision", "fieldname": "decision_days", "fieldtype": "Int", "width": 120},
]


def execute(filters=None):
    filters = frappe._dict(filters or {})

    query_filters = {}
    query_filters.update(scope.territory_filter(frappe.session.user, "territory"))
    if filters.get("territory"):
        query_filters["territory"] = filters.territory
    if filters.get("status"):
        query_filters["status"] = filters.status

    rows = frappe.get_all(
        "Customer Onboarding",
        filters=query_filters,
        fields=["name", "customer_name", "territory", "docstatus", "status", "request_date", "decided_on"],
        order_by="request_date desc",
    )

    data = []
    for r in rows:
        status_label = "Draft" if r.docstatus == 0 else (r.status or "Pending")
        decision_days = None
        if r.request_date and r.decided_on:
            decision_days = (getdate(r.decided_on) - getdate(r.request_date)).days
        data.append({
            "name": r.name,
            "customer_name": r.customer_name,
            "territory": r.territory,
            "status_label": status_label,
            "request_date": r.request_date,
            "decided_on": r.decided_on,
            "decision_days": decision_days,
        })
    return COLUMNS, data
