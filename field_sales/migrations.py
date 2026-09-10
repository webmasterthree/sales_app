# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Defensive cleanup for damage caused by the legacy `mohan_impex` app,
still installed alongside field_sales on this shared reference site.

Two separate, unrelated pieces of legacy fixture/hook behaviour keep
undoing fixes made here:

1. `mohan_impex` ships a Property Setter overriding
   `Notification Log.type.options` with a Select list from an older
   Frappe version. In v15 that field is a Link to Notification Type; the
   stale override makes every Notification Log insert throw
   DoesNotExistError, because Frappe tries to resolve the whole options
   string as a single DocType name. A Property Setter that lives in an
   *installed app's* fixtures gets silently re-synced on every
   `bench migrate`, so it has to be removed again after every migrate.

2. `mohan_impex.mohan_impex.employee.set_user_permissions` runs on every
   Employee `on_update` and, in the course of resetting that employee's
   user permissions, ends up stripping the `Sales Executive App` role
   off the shared "TSM" Role Profile. Frappe's User controller syncs a
   User's roles FROM their Role Profile on every save, so once the
   profile loses the role, every TSM user loses PWA access on their next
   save - not just on migrate, but on any ordinary Employee save (e.g.
   from tests, or HR editing an employee record). Re-asserting the role
   on the Role Profile right after Employee.on_update counters this at
   the same point it gets stripped.

3. `mohan_impex` ships TWO doctype-customization files (its own and a
   nested `fmcg_cp` module's) that both bake `ignore_user_permissions: 0`
   onto `Customer.created_by_emp` - a "who created this" tracking field
   that a User Permission on Employee accidentally turns into a
   document-level access gate: any Customer created by/attributed to a
   *different* employee than the viewing rep becomes unreadable to them,
   even though the bare doctype-level read permission is granted. Setting
   `ignore_user_permissions: 1` disables that accidental gate. Frappe
   re-syncs an app's `custom/<doctype>.json` files on every `bench
   migrate` unconditionally - unlike fixtures, this isn't even gated by
   the app's own `fixtures` hook - so the flag reverts on every migrate
   until this is re-applied here too.
"""

import frappe

BAD_PROPERTY_SETTERS = [
    ("Notification Log", "type", "options"),
]

REQUIRED_ROLE_PROFILE_ROLES = [
    ("TSM", "Sales Executive App"),
]

IGNORE_USER_PERMISSIONS_FIELDS = [
    ("Customer", "created_by_emp"),
]


def after_migrate():
    _fix_bad_property_setters()
    _fix_role_profiles()
    _fix_ignore_user_permissions()


def ensure_role_profiles(doc=None, method=None):
    """Hooked onto Employee.on_update - re-asserts roles that
    mohan_impex's own on_update handler for the same event strips off
    the Role Profile. See module docstring for why this is necessary."""
    _fix_role_profiles()


def _fix_bad_property_setters():
    for doctype, field_name, property_name in BAD_PROPERTY_SETTERS:
        name = frappe.db.get_value(
            "Property Setter",
            {"doc_type": doctype, "field_name": field_name, "property": property_name},
            "name",
        )
        if name:
            frappe.delete_doc("Property Setter", name, ignore_permissions=True, force=True)
            frappe.clear_cache(doctype=doctype)


def _fix_role_profiles():
    for role_profile, role in REQUIRED_ROLE_PROFILE_ROLES:
        if not frappe.db.exists("Role Profile", role_profile):
            continue
        has_role = frappe.db.exists(
            "Has Role", {"parent": role_profile, "parenttype": "Role Profile", "role": role}
        )
        if has_role:
            continue
        profile = frappe.get_doc("Role Profile", role_profile)
        profile.append("roles", {"role": role})
        profile.save(ignore_permissions=True)
        # Role Profile roles only propagate to Users on their own next
        # save - push it now so nobody is left stale until then.
        for user in frappe.get_all("User", {"role_profile_name": role_profile}, pluck="name"):
            frappe.get_doc("User", user).save(ignore_permissions=True)


def _fix_ignore_user_permissions():
    for doctype, fieldname in IGNORE_USER_PERMISSIONS_FIELDS:
        name = frappe.db.get_value(
            "Custom Field", {"dt": doctype, "fieldname": fieldname}, "name"
        )
        if not name:
            continue
        if frappe.db.get_value("Custom Field", name, "ignore_user_permissions"):
            continue
        frappe.db.set_value("Custom Field", name, "ignore_user_permissions", 1)
        frappe.clear_cache(doctype=doctype)
