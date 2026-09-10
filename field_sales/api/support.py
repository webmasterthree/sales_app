# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Support and legal content for the client's Profile screen.

Sourced from the "Field Sales Settings" singleton so an administrator can
edit it from the desk without a deploy - the same doctype already holds the
app's geofencing configuration. Any signed-in user may read it; only System
Manager (per that doctype's own permissions) may write it.
"""

import frappe
from frappe import _


@frappe.whitelist()
def support_info() -> dict:
    """Support contact details shown on Profile."""
    if frappe.session.user == "Guest":
        raise frappe.AuthenticationError(_("Not signed in"))

    settings = frappe.get_single("Field Sales Settings")
    return {
        "phone": settings.support_phone,
        "email": settings.support_email,
        "hours": settings.support_hours,
    }


@frappe.whitelist()
def legal_info() -> dict:
    """Privacy policy and terms of use text/links shown on Profile."""
    if frappe.session.user == "Guest":
        raise frappe.AuthenticationError(_("Not signed in"))

    settings = frappe.get_single("Field Sales Settings")
    return {
        "privacy_policy": settings.privacy_policy,
        "terms_of_use": settings.terms_of_use,
    }
