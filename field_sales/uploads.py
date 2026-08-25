# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Backfills the File<->document link after a create endpoint saves a photo.

A rep uploads a shop photo / KYC document scan / complaint photo BEFORE the
parent record exists (there is no docname yet on a create form), so
`upload_file` on the frontend deliberately omits doctype/docname and lands a
loose, unattached private File - Frappe's own doctype-level permission check
in `upload_file` fails closed for a scoped role when there's no document to
test territory/ownership against, even though the same role can write its
own records fine once one exists (see frontend/src/composables/upload.js for
the full story).

That loose file still works as an Attach/Attach Image value - the field is
just a URL string - but Frappe's file-permission fallback for a *private*
file looks at its own `attached_to_doctype`/`attached_to_name` to decide who
else can read it. Left unset, only the uploading rep can ever view their own
photo again; a manager approving the same KYC request later would hit a 403
on the image. This backfills that link right after the parent document is
inserted, so the normal "can you read the parent doc" permission chain then
covers the file too.
"""

import frappe


def link_uploaded_file(file_url: str | None, doctype: str, docname: str, fieldname: str | None = None) -> None:
    """Point the File record backing `file_url` at the document that now
    owns it, but only if the calling user actually uploaded it - never
    reattach a file just because its URL showed up in someone else's
    payload."""
    if not file_url:
        return

    file_name = frappe.db.get_value(
        "File", {"file_url": file_url, "owner": frappe.session.user}, "name"
    )
    if not file_name:
        return

    frappe.db.set_value(
        "File", file_name,
        {"attached_to_doctype": doctype, "attached_to_name": docname, "attached_to_field": fieldname},
        update_modified=False,
    )
