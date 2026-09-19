# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Desk version of the PWA's own Collections report - same computation
(field_sales.api.customers.collections_report), scoped by whichever Desk
user runs it."""

import frappe

from field_sales.api.customers import collections_report

COLUMNS = [
    {"label": "Customer", "fieldname": "name", "fieldtype": "Link", "options": "Customer", "width": 220},
    {"label": "Level", "fieldname": "customer_level", "fieldtype": "Data", "width": 90},
    {"label": "Territory", "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 150},
    {"label": "Outstanding", "fieldname": "outstanding", "fieldtype": "Currency", "width": 130},
    {"label": "Invoices", "fieldname": "invoice_count", "fieldtype": "Int", "width": 80},
    {"label": "Overdue Invoices", "fieldname": "overdue_count", "fieldtype": "Int", "width": 120},
]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    result = collections_report(min_outstanding=filters.get("min_outstanding") or 0)
    return COLUMNS, result["records"]
