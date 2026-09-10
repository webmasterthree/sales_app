# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""The home screen: module grid, scoreboard, check-in state, notifications.

Replaces `mohan_impex.api.dashboard` and `api/profile/notification.py`.

Notable differences from the original:

* the module grid returns client routes and icon names, not signed file URLs -
  the original minted fourteen JWTs per home screen just to serve tile icons;
* the scoreboard is scoped to the signed-in rep and a real period, rather than
  counting every submitted document they ever filed;
* a failure in one panel degrades that panel instead of 500-ing the whole
  screen. The original raised on a missing `Employee Checkin` doctype and took
  the entire home screen down with it.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, get_first_day, get_last_day, getdate, nowdate

from field_sales import scope


def _employee(user: str | None = None) -> str | None:
    return frappe.db.get_value(
        "Employee", {"user_id": user or frappe.session.user, "status": "Active"}, "name"
    )


# ---------------------------------------------------------------- module grid


def module_grid(user: str | None = None) -> list[dict]:
    """Tiles this user may see, nested one level."""
    user = user or frappe.session.user
    rows = frappe.get_all(
        "Field Sales Module",
        filters={"enabled": 1},
        fields=["name", "module_name", "label", "icon", "route",
                "document_type", "parent_module", "is_group", "sort_order"],
        order_by="sort_order asc",
        ignore_permissions=True,
    )

    def visible(row) -> bool:
        if not row.document_type:
            return True
        if not frappe.db.exists("DocType", row.document_type):
            return False
        return bool(frappe.has_permission(row.document_type, "read", user=user))

    children: dict[str, list] = {}
    for row in rows:
        if row.parent_module and visible(row):
            children.setdefault(row.parent_module, []).append(_tile(row))

    grid = []
    for row in rows:
        if row.parent_module:
            continue
        kids = children.get(row.module_name, [])
        if row.is_group:
            # a group with nothing visible under it is not a tile
            if not kids:
                continue
            tile = _tile(row)
            tile["children"] = kids
            grid.append(tile)
        elif visible(row):
            grid.append(_tile(row))
    return grid


def _tile(row) -> dict:
    return {
        "name": row.module_name,
        "label": row.label,
        "icon": row.icon,
        "route": row.route,
        "doctype": row.document_type,
    }


# ---------------------------------------------------------------- scoreboard


SCORES = [
    ("visits", "Visits", "Field Visit", "sales_person", "visit_date"),
    ("orders", "Orders", "Sales Order", None, "transaction_date"),
]


def scoreboard(user: str | None = None, from_date: str | None = None,
               to_date: str | None = None) -> list[dict]:
    """What this rep has filed in the period. Defaults to the current month."""
    user = user or frappe.session.user
    employee = _employee(user)
    from_date = from_date or get_first_day(nowdate())
    to_date = to_date or get_last_day(nowdate())

    out = []
    for key, label, doctype, owner_field, date_field in SCORES:
        entry = {"name": key, "label": label, "count": 0}
        try:
            if not frappe.db.exists("DocType", doctype):
                out.append(entry)
                continue
            filters = {
                "docstatus": 1,
                date_field: ["between", [from_date, to_date]],
            }
            if owner_field and employee:
                filters[owner_field] = employee
            filters.update(scope.territory_filter(user, _territory_field(doctype)))
            entry["count"] = frappe.db.count(doctype, filters=filters)
        except Exception:
            # a broken panel should not take the home screen down
            frappe.clear_last_message()
        out.append(entry)
    return out


def _territory_field(doctype: str) -> str:
    meta = frappe.get_meta(doctype)
    for candidate in ("territory", "fs_territory"):
        if meta.has_field(candidate):
            return candidate
    return "territory"


# ---------------------------------------------------------------- sales target


@frappe.whitelist()
def sales_target(user: str | None = None) -> dict:
    """This rep's sales target for the current month versus what they have
    actually billed, read from ERPNext's own `Sales Person` / `Target
    Detail` / `Monthly Distribution` records - the app is a reader of this
    data, not a parallel system (the same principle behind `scoreboard()`
    reading submitted documents rather than keeping its own counters).

    Returns a percent only when there is a real target to measure against;
    the caller must treat an absent target as "nothing to show" rather than
    defaulting to 0%, which would read as "0% of goal" instead of "no goal
    set" - two very different facts.
    """
    user = user or frappe.session.user
    employee = _employee(user)
    empty = {"has_target": False, "target_amount": 0, "achieved_amount": 0,
             "percent": 0, "month": None}
    if not employee:
        return empty

    sales_person = frappe.db.get_value("Sales Person", {"employee": employee}, "name")
    if not sales_person:
        return empty

    targets = frappe.get_all(
        "Target Detail", filters={"parent": sales_person, "parenttype": "Sales Person"},
        fields=["target_amount", "distribution_id"],
    )
    annual_target = sum(flt(t.target_amount) for t in targets)
    if not annual_target:
        return empty

    today = getdate(nowdate())
    month_name = today.strftime("%B")
    distribution_id = next((t.distribution_id for t in targets if t.distribution_id), None)

    monthly_target = annual_target / 12
    if distribution_id:
        pct = frappe.db.get_value(
            "Monthly Distribution Percentage",
            {"parent": distribution_id, "month": month_name},
            "percentage_allocation",
        )
        if pct:
            monthly_target = annual_target * flt(pct) / 100

    from_date = get_first_day(nowdate())
    to_date = get_last_day(nowdate())
    achieved = _orders_by_employee(from_date, to_date).get(employee, {}).get("value", 0.0)

    percent = round((achieved / monthly_target) * 100) if monthly_target else 0
    return {
        "has_target": True,
        # Rounded here, at the source, rather than left to whichever caller
        # happens to format it - a Monthly Distribution's percentage_allocation
        # is a stored decimal (e.g. 100/12 = 8.333...%), so the raw computed
        # amount is very rarely a clean rupee figure even when the underlying
        # target obviously should be (an even 12-way split of ₹5,40,000 comes
        # back as ₹44,999.999998, not ₹45,000, without this).
        "target_amount": round(monthly_target, 2),
        "achieved_amount": round(achieved, 2),
        "percent": min(percent, 999),  # cap the display, not the underlying fact of over-achieving
        "month": month_name,
    }


# ---------------------------------------------------------------- orders-by-rep


def _orders_by_employee(from_date: str, to_date: str,
                         territory_filters: dict | None = None) -> dict[str, dict]:
    """Submitted Sales Orders attributed to each rep, keyed by **Employee**
    (the id space `Field Visit.sales_person` and every other rep-scoping
    field in this app uses), via ERPNext's own `Sales Team` child table.

    Two things worth remembering here, both real bugs caught building this:

    `Sales Order` carries no `fs_sales_person` field - that field was never
    added to this doctype, so any filter keyed on it (as `leaderboard()` did
    before this) silently matches nothing. A rep's attribution is native
    ERPNext instead: a `Sales Team` row per order, each with its own
    `allocated_percentage` (a deal can be split across reps) - joining
    through that table honours the split so a 50%-allocated order counts as
    half a sale for that rep, not a full one.

    `Sales Team.sales_person` links to the **Sales Person** doctype, not
    Employee - a different id space from `Field Visit.sales_person`, which
    links to Employee directly. Mixing the two without translating produces
    two disjoint sets of rows for the same person instead of one merged
    total, so this resolves every Sales Person back to its linked Employee
    before returning.
    """
    order_filters = {"docstatus": 1, "transaction_date": ["between", [from_date, to_date]]}
    if territory_filters:
        order_filters.update(territory_filters)
    order_names = frappe.get_all("Sales Order", filters=order_filters, pluck="name")
    if not order_names:
        return {}

    team_rows = frappe.get_all(
        "Sales Team",
        filters={"parent": ["in", order_names], "parenttype": "Sales Order"},
        fields=["parent", "sales_person", "allocated_percentage"],
    )
    totals = {
        r.name: flt(r.grand_total)
        for r in frappe.get_all(
            "Sales Order", filters={"name": ["in", order_names]},
            fields=["name", "grand_total"],
        )
    }
    sp_to_employee = {
        r.name: r.employee
        for r in frappe.get_all(
            "Sales Person",
            filters={"name": ["in", list({row.sales_person for row in team_rows if row.sales_person})]},
            fields=["name", "employee"],
        )
    }

    out: dict[str, dict] = {}
    for row in team_rows:
        employee = sp_to_employee.get(row.sales_person)
        if not employee:
            continue
        entry = out.setdefault(employee, {"count": 0, "value": 0.0})
        entry["count"] += 1
        share = (flt(row.allocated_percentage) or 100) / 100
        entry["value"] += totals.get(row.parent, 0.0) * share
    return out


# ---------------------------------------------------------------- leaderboard


@frappe.whitelist()
def leaderboard(from_date: str | None = None, to_date: str | None = None) -> list[dict]:
    """Submitted visits and orders per rep, scoped to the caller's territory.

    There is no dedicated leaderboard doctype in this app, so this is a
    straight aggregation over the same submitted Field Visit / Sales Order
    records `scoreboard()` already counts for one rep - just grouped by
    `sales_person` instead of filtered to one. A rep with an unrestricted
    scope (a manager) sees their whole territory; anyone else sees only
    their own row, since `territory_filter` narrows the query the same way
    it does everywhere else.
    """
    user = frappe.session.user
    from_date = from_date or get_first_day(nowdate())
    to_date = to_date or get_last_day(nowdate())

    visit_filters = {"docstatus": 1, "visit_date": ["between", [from_date, to_date]]}
    visit_filters.update(scope.territory_filter(user, "territory"))
    visits = frappe.get_all(
        "Field Visit",
        filters=visit_filters,
        group_by="sales_person",
        fields=["sales_person", "sales_person_name", "count(name) as visits"],
    )

    orders = _orders_by_employee(
        from_date, to_date, scope.territory_filter(user, "territory")
    )

    # both dicts are keyed by Employee - see _orders_by_employee's docstring
    # for why that translation matters.
    board: dict[str, dict] = {}
    for row in visits:
        if not row.sales_person:
            continue
        board[row.sales_person] = {
            "sales_person": row.sales_person,
            "sales_person_name": row.sales_person_name,
            "visits": cint(row.visits),
            "orders": 0,
            "order_value": 0,
        }
    for employee, totals in orders.items():
        entry = board.setdefault(employee, {
            "sales_person": employee,
            "sales_person_name": frappe.db.get_value("Employee", employee, "employee_name"),
            "visits": 0,
            "orders": 0,
            "order_value": 0,
        })
        entry["orders"] = totals["count"]
        entry["order_value"] = totals["value"]

    ranked = sorted(board.values(), key=lambda r: (r["visits"], r["orders"]), reverse=True)
    for i, row in enumerate(ranked, start=1):
        row["rank"] = i
    return ranked


# ---------------------------------------------------------------- check-in


def check_in_state(user: str | None = None) -> dict:
    """The rep's last attendance punch, from HRMS.

    Returns an empty state rather than raising when HRMS is absent - the
    original 500-ed the whole dashboard in that case.
    """
    employee = _employee(user)
    state = {"employee": employee, "last_type": None, "last_time": None,
             "checked_in": False}
    if not employee or not frappe.db.exists("DocType", "Employee Checkin"):
        return state

    last = frappe.get_all(
        "Employee Checkin",
        filters={"employee": employee},
        fields=["log_type", "time"],
        # two punches can land in the same second, so break the tie on
        # insertion order rather than letting the database choose
        order_by="time desc, creation desc",
        limit=1,
    )
    if last:
        state["last_type"] = last[0].log_type
        state["last_time"] = last[0].time
        state["checked_in"] = last[0].log_type == "IN"
    return state


@frappe.whitelist(methods=["POST"])
def punch(log_type: str, latitude=None, longitude=None):
    """Record an attendance punch."""
    if log_type not in ("IN", "OUT"):
        frappe.throw(_("log_type must be IN or OUT."))
    employee = _employee()
    if not employee:
        frappe.throw(_("Your user is not linked to an active Employee."))
    if not frappe.db.exists("DocType", "Employee Checkin"):
        frappe.throw(_("Attendance requires the HR app to be installed."))

    doc = frappe.new_doc("Employee Checkin")
    doc.update({
        "employee": employee,
        "log_type": log_type,
        "time": frappe.utils.now_datetime(),
    })
    if latitude is not None and longitude is not None:
        doc.latitude = latitude
        doc.longitude = longitude
    doc.flags.ignore_validate = True
    doc.insert(ignore_permissions=True)
    return check_in_state()


# ---------------------------------------------------------------- notifications


@frappe.whitelist()
def notifications(unread_only: int = 0, limit: int = 20):
    """Native Notification Log for the signed-in user."""
    filters = {"for_user": frappe.session.user}
    if cint(unread_only):
        filters["read"] = 0

    rows = frappe.get_all(
        "Notification Log",
        filters=filters,
        fields=["name", "subject", "type", "document_type", "document_name",
                "from_user", "read", "creation"],
        order_by="creation desc",
        limit=cint(limit) or 20,
    )
    return {
        "records": rows,
        "unread_count": frappe.db.count(
            "Notification Log", {"for_user": frappe.session.user, "read": 0}
        ),
    }


@frappe.whitelist(methods=["POST"])
def mark_notification_read(name: str | None = None, all_of_them: int = 0):
    """Mark one notification read, or every one."""
    if cint(all_of_them):
        frappe.db.set_value(
            "Notification Log", {"for_user": frappe.session.user, "read": 0},
            "read", 1, update_modified=False,
        )
        return {"unread_count": 0}

    if not name:
        frappe.throw(_("Give a notification to mark, or ask for all of them."))

    owner = frappe.db.get_value("Notification Log", name, "for_user")
    if owner != frappe.session.user:
        raise frappe.PermissionError
    frappe.db.set_value("Notification Log", name, "read", 1, update_modified=False)
    return {
        "unread_count": frappe.db.count(
            "Notification Log", {"for_user": frappe.session.user, "read": 0}
        )
    }


# ---------------------------------------------------------------- the screen


@frappe.whitelist()
def home():
    """Everything the home screen needs, in one call."""
    user = frappe.session.user
    return {
        "user": {
            "name": user,
            "full_name": frappe.db.get_value("User", user, "full_name"),
            "employee": _employee(user),
            "territories": scope.effective_territories(user),
        },
        "modules": module_grid(user),
        "scoreboard": scoreboard(user),
        "attendance": check_in_state(user),
        "unread_notifications": frappe.db.count(
            "Notification Log", {"for_user": user, "read": 0}
        ),
    }
