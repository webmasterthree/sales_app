import frappe
from frappe.boot import load_translations

from field_sales.api import branding

no_cache = 1


def get_context(context):
    csrf_token = frappe.sessions.get_csrf_token()
    frappe.db.commit()  # nosemgrep
    context = frappe._dict()
    context.csrf_token = csrf_token
    context.boot = get_boot()
    context.site_name = frappe.local.site
    # Rendered directly into <title>/apple-mobile-web-app-title (see
    # frontend/index.html) - those need the real text at first paint, unlike
    # the manifest/favicon which just point at branding.py's own endpoints
    # and can go stale-then-fresh on the next request instead.
    context.app_name = branding.get_app_name()
    return context


@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_context_for_dev():
    if not frappe.conf.developer_mode:
        frappe.throw(frappe._("This method is only meant for developer mode"))
    return get_boot()


def get_boot():
    bootinfo = frappe._dict(
        {
            "site_name": frappe.local.site,
            "default_route": "/field_sales_app",
        }
    )
    bootinfo.lang = frappe.local.lang
    load_translations(bootinfo)
    # This page builds its own minimal bootinfo rather than going through
    # frappe.sessions.get_boot_info(), which is the only place the standard
    # extend_bootinfo hook mechanism actually runs - so notification_relay's
    # own extend_bootinfo (which supplies this same key for the Desk/HRMS
    # boot path) never fires here. Read it directly instead.
    bootinfo.push_relay_server_url = frappe.conf.get("push_relay_server_url")
    # Lets screens rendered client-side (Login, Settings, ...) show the same
    # configurable name/icon as <title> and the manifest, without a second
    # round trip to branding.py's own endpoints just to read what's already
    # being computed here anyway.
    bootinfo.app_name = branding.get_app_name()
    bootinfo.app_icon = branding.get_icon_path()
    # Raw, not branding.get_app_description() - that function's own fallback
    # ("Field sales, visits, orders and approvals.") is written for the PWA
    # manifest, not as login-page copy. Login.vue has its own, more
    # contextual fallback ("Sign in to log visits...") for when nothing's
    # been configured, and needs to tell "nothing set" apart from "the
    # manifest's default happens to be set" to fall back to it correctly.
    bootinfo.app_description = frappe.db.get_single_value("Field Sales Branding", "app_description")
    return bootinfo
