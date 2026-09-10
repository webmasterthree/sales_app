import frappe

from field_sales.api import branding

# Where a Notification Log's document_type routes to inside this PWA, mirroring
# frontend/src/views/Notifications.vue's own DETAIL_ROUTES map - keep the two
# in sync. A document_type not listed here still gets a push, just linking to
# the app's home screen instead of the specific record.
DETAIL_ROUTES = {
    "Field Visit": "visits",
    "Customer Onboarding": "onboarding",
    "Product Demo": "requisitions/demos",
    "Sample Request": "requisitions/samples",
    "Collateral Request": "requisitions/collateral",
    "Issue": "complaints",
    "Sales Order": "orders",
    "Customer": "customers",
}


def send_push_for_notification_log(doc, method=None):
    """Relay a newly created core Notification Log entry to the recipient's
    registered devices via Firebase.

    field_sales already stores its in-app notifications in Frappe's own
    Notification Log (see api/home.py's notifications()) rather than a
    dedicated doctype, so this hooks onto that same insert instead of
    duplicating it - one entry point covers every existing source (ToDo
    assignments, mentions, energy points, etc.) plus anything the app itself
    creates later, with no extra wiring needed per event.
    """
    if not doc.for_user:
        return

    try:
        from frappe.push_notification import PushNotification

        push_notification = PushNotification("field_sales")
        if not push_notification.is_enabled():
            return

        push_notification.send_notification_to_user(
            doc.for_user,
            doc.subject or doc.title or "Notification",
            doc.email_content or doc.subject or "",
            link=_get_link(doc),
            icon=_public_url(branding.get_icon_path()),
        )
    except ImportError:
        # notification_relay / push notification support isn't available on
        # this framework version - nothing to relay, in-app list still works.
        pass
    except Exception:
        frappe.log_error(title="field_sales push notification", message=frappe.get_traceback())


def _get_link(doc):
    base_url = f"{_public_url('')}/field_sales_app"
    route = DETAIL_ROUTES.get(doc.document_type)
    if route and doc.document_name:
        return f"{base_url}/{route}/{doc.document_name}"
    return base_url


def _public_url(path: str) -> str:
    """An absolute URL a user's device can actually reach - unlike
    frappe.utils.get_url(), which returns the site's configured host_name
    unconditionally when one is set, regardless of which domain the request
    actually came in on. On this site host_name is an internal-only
    hostname with no public DNS record, so a push notification's icon/link
    built from get_url() 404s (or fails to resolve at all) on every real
    device - this prefers the real incoming request's own Host header, and
    only falls back to get_url() when there's no request to read one from
    (e.g. triggered from bench console rather than a live user action).
    """
    host = frappe.utils.get_host_name_from_request()
    base = host or frappe.utils.get_url()
    return f"{base}{path}"
