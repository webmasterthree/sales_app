# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Territory scoping: who is allowed to see which records.

Every list in the field sales app is scoped to the viewer's territory and
everything beneath it in the territory tree. The implementation this replaces
built that scope by pasting territory names straight into a SQL string::

    areas = "', '".join(consolidated_territory)
    return f"area in ('{areas}') "

which is a SQL injection carried on master data, and it also bypassed Frappe's
permission layer entirely. Everything here returns *filters*, never SQL, so
values are always parameterised by the query builder.

Scope is resolved in this order:

1. ``User Permission`` rows on Territory for the user - the explicit grant.
2. Otherwise the employee's own ``area``.

The fallback matters: ERPNext's Employee doctype maintains its own User
Permission rows and can remove ones it did not create, so an installation can
silently lose its Territory grants. Falling back to ``Employee.area`` keeps a
rep scoped to their own patch instead of failing open.
"""

import frappe
from frappe.utils.nestedset import get_descendants_of

TERRITORY_DOCTYPE = "Territory"


def _user(user: str | None = None) -> str:
    return user or frappe.session.user


def granted_territories(user: str | None = None) -> list[str]:
    """Territories explicitly granted to the user via User Permission."""
    return frappe.get_all(
        "User Permission",
        filters={"user": _user(user), "allow": TERRITORY_DOCTYPE},
        pluck="for_value",
        ignore_permissions=True,
    )


def employee_territory(user: str | None = None) -> str | None:
    """The territory on the user's own Employee record, if any."""
    return frappe.db.get_value(
        "Employee", {"user_id": _user(user), "status": "Active"}, "area"
    )


def resolve_leaf_territory(
    value: str | None, employee: str | None = None, fallback_user: str | None = None
) -> str | None:
    """A real, specific territory - falling back when the given one is unusable.

    Frappe pre-populates any new document's field from the *system default*
    of the same name before ``validate()`` ever runs (via
    ``Document._set_defaults`` -> ``update_if_missing``). ERPNext's setup
    wizard sets a system default of "All Territories" for the fieldname
    "territory", so a controller pattern like::

        if self.territory or not self.sales_person:
            return
        self.territory = frappe.db.get_value("Employee", self.sales_person, "area")

    never fires: the field already looks set. Worse, that default is a group
    territory, so a rep who leaves the field blank silently gets scoped to
    the whole tree rather than being caught by the field's own ``reqd``
    check, which runs *after* the default has already filled it in.

    Use this instead of a bare truthiness check wherever a document falls
    back to a territory. Pass ``employee`` when the document already knows
    which Employee it belongs to (its own ``sales_person``, say) - falling
    back to the *signed-in* user instead would resolve the wrong person's
    territory whenever a manager or admin is filing the record on a rep's
    behalf. ``fallback_user`` is for callers with no employee reference at
    all, such as a bare API caller acting on their own account.
    """
    if value and not frappe.db.get_value("Territory", value, "is_group"):
        return value
    if employee:
        return frappe.db.get_value("Employee", employee, "area")
    return employee_territory(fallback_user)


def effective_territories(user: str | None = None, include_descendants: bool = True) -> list[str]:
    """Every territory the user may see, including child territories.

    Returns an empty list for a user with no territory at all, which callers
    must read as "nothing", never as "everything".
    """
    user = _user(user)

    roots = [t for t in granted_territories(user) if t]
    if not roots:
        own = employee_territory(user)
        roots = [own] if own else []

    if not roots:
        return []

    scope: set[str] = set(roots)
    if include_descendants:
        for territory in roots:
            try:
                scope.update(get_descendants_of(TERRITORY_DOCTYPE, territory))
            except Exception:
                # A stale grant pointing at a deleted territory must narrow the
                # scope, not break the request.
                continue

    return sorted(scope)


def has_unrestricted_scope(user: str | None = None) -> bool:
    """System users who are not scoped to a territory at all."""
    user = _user(user)
    if user == "Administrator":
        return True
    roles = set(frappe.get_roles(user))
    return bool(roles & {"System Manager", "Sales Master Manager"})


def territory_filter(user: str | None = None, fieldname: str = "area") -> dict:
    """A Frappe filter dict scoping a query to the user's territories.

    Use with ``frappe.get_all`` / ``frappe.qb`` so values are parameterised::

        frappe.get_all("Field Visit", filters=territory_filter())

    An unscoped user gets ``{}`` - no restriction. A scoped user with no
    territory gets a filter that matches nothing, so the failure mode is an
    empty list rather than someone else's data.
    """
    if has_unrestricted_scope(user):
        return {}

    territories = effective_territories(user)
    if not territories:
        return {fieldname: ["in", []]}

    return {fieldname: ["in", territories]}


def owner_filter(user: str | None = None, fieldname: str = "created_by_emp") -> dict:
    """Restrict to records the user's own employee created."""
    employee = frappe.db.get_value("Employee", {"user_id": _user(user)}, "name")
    return {fieldname: employee or ""}


def scoped_filters(
    user: str | None = None,
    fieldname: str = "area",
    mine_only: bool | None = None,
    owner_fieldname: str = "created_by_emp",
) -> dict:
    """Territory scope, optionally narrowed to the user's own records.

    ``mine_only`` mirrors the mine / my-team toggle on the app's list screens.
    """
    filters = dict(territory_filter(user, fieldname))
    if mine_only:
        filters.update(owner_filter(user, owner_fieldname))
    return filters
