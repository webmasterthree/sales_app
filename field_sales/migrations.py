# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Defensive post-migrate cleanup.

`mohan_impex` - the legacy client app still installed alongside field_sales
on this shared reference site - ships a Property Setter overriding
`Notification Log.type.options` with a Select list from an older Frappe
version. In v15 that field is a Link to Notification Type; the stale
override makes every Notification Log insert throw DoesNotExistError,
because Frappe tries to resolve the whole options string as a single
DocType name.

This was found and removed once already, directly against the database -
but a Property Setter that lives in an *installed app's* fixtures gets
silently re-synced on the next `bench migrate`, undoing a one-off manual
fix. Removing it here, on every migrate, is what actually makes the fix
stick on a site that still carries mohan_impex.
"""

import frappe

BAD_PROPERTY_SETTERS = [
    ("Notification Log", "type", "options"),
]


def after_migrate():
    for doctype, field_name, property_name in BAD_PROPERTY_SETTERS:
        name = frappe.db.get_value(
            "Property Setter",
            {"doc_type": doctype, "field_name": field_name, "property": property_name},
            "name",
        )
        if name:
            frappe.delete_doc("Property Setter", name, ignore_permissions=True, force=True)
            frappe.clear_cache(doctype=doctype)
