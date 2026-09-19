# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""A safe, reusable list endpoint.

The app this replaces hand-rolled the same paginated list about ten times -
visits, orders, KYC, journey plans, samples, collateral, complaints, customers,
trials, schemes - each around a hundred lines of SQL assembled by string
formatting::

    query += ''' AND (shop_name LIKE "%{search_text}%") '''.format(
        search_text=frappe.form_dict.get("search_text"))

Every one of those is an injection carried on user input, and they bypass
Frappe's permission layer as a side effect. This module is the single
replacement: callers declare *what* is listable and the helper builds the
query with parameterised filters.

Three things are deliberately strict:

* **search** becomes a `like` filter *value*, never SQL text, so the query
  builder parameterises it;
* **filters** must be declared - an undeclared query parameter is ignored
  rather than trusted;
* **order_by** is validated against the declared fields, because it is the one
  clause Frappe interpolates rather than binds.
"""

import math

import frappe
from frappe import _
from frappe.utils import cint

from field_sales import scope

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20
SORT_DIRECTIONS = ("asc", "desc")


class ListConfig:
    """Declares what may be listed, searched, filtered and sorted."""

    def __init__(
        self,
        doctype: str,
        fields: list[str],
        search_fields: list[str] | None = None,
        filter_fields: dict[str, str] | None = None,
        territory_field: str | None = "area",
        owner_field: str | None = "created_by_emp",
        default_order: str = "creation desc",
        sortable_fields: list[str] | None = None,
        tabs: dict[str, dict] | None = None,
        base_filters: dict | None = None,
    ):
        self.doctype = doctype
        self.fields = fields
        self.search_fields = search_fields or []
        # query-parameter name -> real fieldname
        self.filter_fields = filter_fields or {}
        self.territory_field = territory_field
        self.owner_field = owner_field
        self.default_order = default_order
        # what a caller may sort by; defaults to the selected fields
        self.sortable_fields = sortable_fields or list(fields)
        # named tabs, e.g. {"draft": {"docstatus": 0}}
        self.tabs = tabs or {}
        # filters always applied, regardless of what the caller asks for -
        # e.g. narrowing "Pricing Rule" down to just discount schemes
        self.base_filters = base_filters or {}

    def resolve_order_by(self, requested: str | None) -> str:
        """Validate a sort request against the declared fields.

        `order_by` is interpolated into SQL by Frappe, so an unchecked value
        here would reintroduce exactly the hole this module exists to close.
        """
        if not requested:
            return self.default_order

        parts = str(requested).strip().split()
        field = parts[0]
        direction = parts[1].lower() if len(parts) > 1 else "desc"

        if field not in self.sortable_fields or direction not in SORT_DIRECTIONS:
            return self.default_order
        return f"{field} {direction}"


def _pagination(form) -> tuple[int, int, int]:
    page = max(cint(form.get("current_page")) or 1, 1)
    size = cint(form.get("limit")) or DEFAULT_PAGE_SIZE
    size = max(1, min(size, MAX_PAGE_SIZE))
    return page, size, (page - 1) * size


def build_filters(config: ListConfig, form, user: str | None = None) -> tuple[dict, list]:
    """Return (filters, or_filters) for frappe.get_all.

    Values are passed through as data. Nothing here produces SQL text.
    """
    filters: dict = dict(config.base_filters)

    # named tab, e.g. draft vs submitted
    tab = form.get("tab")
    if tab and tab in config.tabs:
        filters.update(config.tabs[tab])

    # declared filters only - anything else in the request is ignored
    for param, fieldname in config.filter_fields.items():
        if param not in form:
            continue
        value = form.get(param)
        if value in ("", None):
            continue
        filters[fieldname] = value

    # territory scope
    if config.territory_field:
        filters.update(scope.territory_filter(user, config.territory_field))

    # mine / my team toggle
    is_self = form.get("is_self")
    if is_self not in ("", None) and config.owner_field:
        employee = frappe.db.get_value(
            "Employee", {"user_id": user or frappe.session.user}, "name"
        )
        if cint(is_self):
            filters[config.owner_field] = employee or ""
        else:
            filters[config.owner_field] = ["!=", employee or ""]

    # search - a like *value*, parameterised by the query builder
    or_filters = []
    text = (form.get("search_text") or "").strip()
    if text and config.search_fields:
        pattern = "%{0}%".format(text)
        or_filters = [[config.doctype, f, "like", pattern] for f in config.search_fields]

    return filters, or_filters


def paginated_list(
    config: ListConfig,
    form=None,
    user: str | None = None,
    extra_filters: dict | None = None,
) -> dict:
    """Run a scoped, searchable, paginated list.

    ``extra_filters`` is for scoping a caller can't express through
    ``ListConfig`` itself - e.g. distributor_list's "has a Secondary
    customer in my territory" check, which filters on a *different*
    doctype's rows than the one being listed, so the generic
    ``territory_field`` mechanism (which only ever looks at the listed
    doctype's own field) can't express it. Applied after every other
    filter, so it can only narrow a request, never loosen one.
    """
    form = frappe._dict(form if form is not None else (frappe.form_dict or {}))
    user = user or frappe.session.user

    if not frappe.has_permission(config.doctype, "read", user=user):
        raise frappe.PermissionError(
            _("Not permitted to read {0}").format(config.doctype)
        )

    page, size, offset = _pagination(form)
    filters, or_filters = build_filters(config, form, user)
    if extra_filters:
        filters.update(extra_filters)
    order_by = config.resolve_order_by(form.get("order_by"))

    records = frappe.get_all(
        config.doctype,
        filters=filters,
        or_filters=or_filters or None,
        fields=config.fields,
        order_by=order_by,
        start=offset,
        page_length=size,
    )

    total = frappe.db.count(config.doctype, filters=filters) if not or_filters else len(
        frappe.get_all(
            config.doctype,
            filters=filters,
            or_filters=or_filters,
            fields=["name"],
            limit_page_length=0,
        )
    )

    return {
        "records": records,
        "total_count": total,
        "page_count": math.ceil(total / size) if size else 0,
        "current_page": page,
        "page_size": size,
        "can_create": frappe.has_permission(config.doctype, "create", user=user),
    }
