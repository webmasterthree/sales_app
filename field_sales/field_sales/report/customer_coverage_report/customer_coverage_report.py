# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Desk version of the PWA's own Customer Coverage report - same
computation (field_sales.api.customers.coverage_report), scoped by
whichever Desk user runs it (a manager sees their whole territory, since
scope.has_unrestricted_scope() covers System Manager / Sales Master
Manager, same as everywhere else in this app)."""

import frappe

from field_sales.api.customers import coverage_report

COLUMNS = [
    {"label": "Customer", "fieldname": "name", "fieldtype": "Link", "options": "Customer", "width": 220},
    {"label": "Level", "fieldname": "customer_level", "fieldtype": "Data", "width": 90},
    {"label": "Territory", "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 150},
    {"label": "Last Visit", "fieldname": "last_visit_date", "fieldtype": "Date", "width": 100},
    {"label": "Days Since Visit", "fieldname": "days_since", "fieldtype": "Int", "width": 110},
]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    result = coverage_report(min_days=filters.get("min_days") or 30)
    return COLUMNS, result["records"]
