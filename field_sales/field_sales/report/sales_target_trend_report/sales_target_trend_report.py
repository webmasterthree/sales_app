# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Desk version of the PWA's own Sales Target trend - same computation
(field_sales.api.home.sales_target_history), so the two can never drift
apart. Lets a manager check any rep's trend via the Sales Rep filter,
rather than only the signed-in rep's own numbers the app itself shows."""

import frappe

from field_sales.api.home import sales_target_history

COLUMNS = [
    {"label": "Month", "fieldname": "label", "fieldtype": "Data", "width": 100},
    {"label": "Target Amount", "fieldname": "target_amount", "fieldtype": "Currency", "width": 140},
    {"label": "Achieved Amount", "fieldname": "achieved_amount", "fieldtype": "Currency", "width": 140},
    {"label": "Percent", "fieldname": "percent", "fieldtype": "Percent", "width": 90},
]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    result = sales_target_history(
        user=filters.get("user") or None,
        months=filters.get("months") or 6,
    )
    if not result.get("has_target"):
        return COLUMNS, []
    return COLUMNS, result["months"]
