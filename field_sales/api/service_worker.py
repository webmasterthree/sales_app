# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Serves the built service worker from a URL whose default scope actually
covers the app.

The built file lives at /assets/field_sales/frontend/sw.js, and a service
worker's scope defaults to its own script's directory unless the server
says otherwise - so registering it straight from that assets path gave it
scope /assets/field_sales/frontend/, which never covers /field_sales_app at
all. Chrome (and every other browser) only offers "Install app" once a
registered, controlling service worker's scope covers the page - so the
real, pre-existing bug here wasn't cosmetic, it silently made the whole app
uninstallable from the very first deploy of push notifications.

Re-serving the exact same file through this whitelisted endpoint instead -
with an explicit Service-Worker-Allowed: / header - lets main.js register
it with scope "/" without moving or duplicating the built file itself.
"""

import frappe
from frappe.utils.response import Response


@frappe.whitelist(allow_guest=True, methods=["GET"])
def script():
    path = frappe.get_app_path("field_sales", "public", "frontend", "sw.js")
    with open(path, "rb") as f:
        body = f.read()

    response = Response()
    response.mimetype = "application/javascript"
    response.data = body
    response.headers["Service-Worker-Allowed"] = "/"
    # A stale cached copy of the service worker script itself is exactly
    # how a rep ends up running last month's app shell indefinitely -
    # browsers already re-check a SW script's bytes on their own schedule,
    # but an intermediary (nginx, a CDN) serving a long-cached copy of this
    # endpoint would defeat that entirely.
    response.headers["Cache-Control"] = "no-cache"
    return response
