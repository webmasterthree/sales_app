import frappe
from frappe.boot import load_translations

no_cache = 1


def get_context(context):
    csrf_token = frappe.sessions.get_csrf_token()
    frappe.db.commit()  # nosemgrep
    context = frappe._dict()
    context.csrf_token = csrf_token
    context.boot = get_boot()
    context.site_name = frappe.local.site
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
    return bootinfo
