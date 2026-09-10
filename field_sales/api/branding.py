# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""App name/icon, configurable via the Field Sales Branding Single doctype
instead of baked into the build - see the app shell (frontend/index.html)
for the two places this actually surfaces:

- <title>/apple-mobile-web-app-title need the real text at first paint, so
  those are rendered server-side as Jinja (see www/field_sales_app.py's
  get_context, which passes app_name into the template).
- <link rel="manifest"> and <link rel="icon"> both point at fixed URLs
  below (manifest()/icon()) rather than being templated - what those URLs
  *return* changes with the doctype, the URLs themselves never do.
"""

import json
import mimetypes

import frappe
from frappe.utils.response import Response

DEFAULT_APP_NAME = "Field Sales"
DEFAULT_APP_DESCRIPTION = "Field sales, visits, orders and approvals."
DEFAULT_ICON_PATH = "/assets/field_sales/manifest/icon-512.png"


def get_app_name() -> str:
    return frappe.db.get_single_value("Field Sales Branding", "app_name") or DEFAULT_APP_NAME


def get_app_description() -> str:
    return frappe.db.get_single_value("Field Sales Branding", "app_description") or DEFAULT_APP_DESCRIPTION


def get_icon_path() -> str:
    """A path relative to the site root - always a public file (enforced by
    Field Sales Branding's own validate()), so this is safe to hand to a
    guest with no permission check."""
    return frappe.db.get_single_value("Field Sales Branding", "app_icon") or DEFAULT_ICON_PATH


@frappe.whitelist(allow_guest=True, methods=["GET"])
def manifest():
    """The PWA's web app manifest, built fresh on every request instead of
    generated once at build time (vite.config.js sets `manifest: false` so
    vite-plugin-pwa never writes/injects its own) - the only way a name/icon
    changed in Desk actually reaches "Add to Home Screen" without a rebuild.
    """
    icon_path = get_icon_path()
    # A relative path, not frappe.utils.get_url(icon_path) - the manifest is
    # fetched by whichever public domain the browser is actually on, and a
    # relative icons[].src resolves against that same domain automatically.
    # get_url() instead returns the site's configured host_name regardless
    # of the request - on this site that's a purely internal hostname with
    # no public DNS record at all, so an icon built from it 404s for every
    # real visitor and silently fails Chrome's installability check (no
    # loadable >=192px icon = no "Install app", ever, no matter how correct
    # everything else about the manifest is).
    icon_url = icon_path
    # The field description asks for a PNG, but nothing enforces that - a
    # declared type that doesn't match the actual file (e.g. a real .jpg
    # advertised as image/png) makes some browsers silently refuse the icon
    # rather than just displaying it wrong, so this reads the real type from
    # the file's own extension instead of assuming one.
    icon_type = mimetypes.guess_type(icon_path)[0] or "image/png"
    app_name = get_app_name()

    body = {
        "name": app_name,
        "short_name": app_name,
        "description": get_app_description(),
        "start_url": "/field_sales_app",
        "display": "standalone",
        "theme_color": "#0F0B17",
        "background_color": "#0F0B17",
        "icons": [
            {"src": icon_url, "sizes": "192x192", "type": icon_type, "purpose": "any"},
            {"src": icon_url, "sizes": "192x192", "type": icon_type, "purpose": "maskable"},
            {"src": icon_url, "sizes": "512x512", "type": icon_type, "purpose": "any"},
            {"src": icon_url, "sizes": "512x512", "type": icon_type, "purpose": "maskable"},
        ],
    }
    response = Response()
    response.mimetype = "application/manifest+json"
    response.data = json.dumps(body)
    return response


@frappe.whitelist(allow_guest=True, methods=["GET"])
def icon():
    """Redirects to whatever the current app icon actually is - one URL
    that never changes for the favicon link, the manifest, and (see
    notify.py) the push notification icon, no matter how many times the
    Field Sales Branding doctype is edited."""
    frappe.local.response["type"] = "redirect"
    # Relative, same reason as manifest()'s own icon_url above - never
    # frappe.utils.get_url(), which can point at a domain the browser
    # can't actually reach.
    frappe.local.response["location"] = get_icon_path()
