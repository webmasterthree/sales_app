# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Desk version of the PWA's own Visit Report - same question (for this
date, which reps had a Journey Plan, and did they actually log a Field
Visit, where), same answer, since this just calls the same correlation
function the app's own `/reports` screen uses. Kept as one source of truth
rather than a second copy of the date+rep matching logic."""

import frappe
from frappe.utils import nowdate

from field_sales.api.journey_plan import journey_plan_visit_report

COLUMNS = [
    {"label": "Sales Person", "fieldname": "sales_person_name", "fieldtype": "Data", "width": 150},
    {"label": "Journey Plan", "fieldname": "journey_plan", "fieldtype": "Link", "options": "Journey Plan", "width": 150},
    {"label": "Territory", "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 120},
    {"label": "Nature of Travel", "fieldname": "nature_of_travel", "fieldtype": "Data", "width": 110},
    {"label": "Field Visit", "fieldname": "visit", "fieldtype": "Link", "options": "Field Visit", "width": 130},
    {"label": "Customer / Prospect", "fieldname": "party", "fieldtype": "Data", "width": 160},
    {"label": "Check In", "fieldname": "check_in", "fieldtype": "Datetime", "width": 150},
    {"label": "Check Out", "fieldname": "check_out", "fieldtype": "Datetime", "width": 150},
    {"label": "Geofence", "fieldname": "geofence_status", "fieldtype": "Data", "width": 90},
    {"label": "Latitude", "fieldname": "latitude", "fieldtype": "Float", "precision": 6, "width": 100},
    {"label": "Longitude", "fieldname": "longitude", "fieldtype": "Float", "precision": 6, "width": 100},
    {"label": "Map", "fieldname": "map_link", "fieldtype": "HTML", "width": 70},
]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    date = filters.date or nowdate()

    plan_rows = journey_plan_visit_report(date)
    if filters.get("sales_person"):
        plan_rows = [r for r in plan_rows if r["sales_person"] == filters.sales_person]
    if filters.get("territory"):
        plan_rows = [r for r in plan_rows if r.get("territory") == filters.territory]

    data = [row for plan in plan_rows for row in _rows_for_plan(plan)]
    return COLUMNS, data


def _rows_for_plan(plan):
    base = {
        "sales_person_name": plan.get("sales_person_name"),
        "journey_plan": plan.get("name"),
        "territory": plan.get("territory"),
        "nature_of_travel": plan.get("nature_of_travel"),
    }
    visits = plan.get("visits") or []
    if not visits:
        yield {**base, "visit": None, "party": None, "check_in": None, "check_out": None,
               "geofence_status": None, "latitude": None, "longitude": None, "map_link": ""}
        return

    for visit in visits:
        lat, lng = visit.get("check_in_latitude"), visit.get("check_in_longitude")
        map_link = (
            f'<a href="https://www.openstreetmap.org/?mlat={lat}&mlon={lng}#map=17/{lat}/{lng}" '
            f'target="_blank" rel="noopener">View</a>'
            if lat and lng else ""
        )
        yield {
            **base,
            "visit": visit.get("name"),
            "party": visit.get("customer_name") or visit.get("prospect_name"),
            "check_in": visit.get("check_in"),
            "check_out": visit.get("check_out"),
            "geofence_status": visit.get("geofence_status"),
            "latitude": lat,
            "longitude": lng,
            "map_link": map_link,
        }
