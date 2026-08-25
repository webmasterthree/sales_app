# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Schemes: the discount-percentage Pricing Rules a rep can quote.

Replaces `api/scheme.py`. A "scheme" was never its own doctype in the original
either - it is a native Pricing Rule with `rate_or_discount = "Discount
Percentage"` - so this stays a read-only view rather than inventing a
parallel doctype for something `field_sales.pricing` already models.
"""

import frappe

from field_sales.api.listing import ListConfig, paginated_list

SCHEME_CONFIG = ListConfig(
    doctype="Pricing Rule",
    fields=[
        "name",
        "title",
        "scheme_type",
        "description",
        "discount_percentage",
        "valid_from",
        "valid_upto",
        "min_qty",
        "max_qty",
    ],
    search_fields=["title", "description"],
    filter_fields={"scheme_type": "scheme_type", "valid_upto": "valid_upto"},
    territory_field=None,
    owner_field=None,
    default_order="valid_upto asc",
    sortable_fields=["title", "valid_from", "valid_upto", "discount_percentage"],
    base_filters={
        "rate_or_discount": "Discount Percentage",
        "selling": 1,
        "disable": 0,
    },
)


@frappe.whitelist()
def scheme_list():
    """Currently-running schemes by default; pass include_expired=1 for all."""
    form = frappe._dict(frappe.form_dict or {})
    if not frappe.utils.cint(form.get("include_expired")):
        # resolved per request, not baked into the static config - "today"
        # cannot be a fixed value on a module-level object
        form["valid_upto"] = [">=", frappe.utils.nowdate()]
    return paginated_list(SCHEME_CONFIG, form=form)


@frappe.whitelist()
def scheme(name: str):
    doc = frappe.get_doc("Pricing Rule", name)
    doc.check_permission("read")
    return doc.as_dict()
