# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Generic comment thread capability.

Every module in this app (Field Visit, Customer Onboarding, Product Demo,
Sample Request, Collateral Request, Complaints, Orders) used to have no way
to leave a note on a record at all - each one only carries its own bare
status field. Rather than bolting a one-off "remarks" thread onto each
doctype separately, this reuses Frappe's own native `Comment` doctype
(the same mechanism the desk's timeline uses) through one small, doctype-
agnostic pair of endpoints.

Scoped to the doctypes this app actually manages - COMMENT_DOCTYPES below -
so a client cannot read or write a comment thread on some unrelated doctype
it happens to know the name of.
"""

import frappe
from frappe import _

COMMENT_DOCTYPES = {
    "Field Visit",
    "Customer Onboarding",
    "Product Demo",
    "Sample Request",
    "Collateral Request",
    "Issue",
    "Sales Order",
}


def _ensure_access(doctype: str, docname: str) -> None:
    if doctype not in COMMENT_DOCTYPES:
        frappe.throw(_("Comments are not available for {0}.").format(doctype))
    # `frappe.has_permission` loads the document itself when given a name,
    # so this both checks the record exists and that the caller may read it -
    # a rep should not be able to read or add a comment on a record outside
    # their own territory just because they can guess its name.
    if not frappe.has_permission(doctype, "read", doc=docname):
        raise frappe.PermissionError


@frappe.whitelist()
def comment_list(doctype: str, docname: str):
    """Every comment on one record, oldest first - a readable history."""
    _ensure_access(doctype, docname)
    return frappe.get_all(
        "Comment",
        filters={
            "reference_doctype": doctype,
            "reference_name": docname,
            "comment_type": "Comment",
        },
        fields=["name", "content", "comment_email", "comment_by", "creation"],
        order_by="creation asc",
    )


@frappe.whitelist(methods=["POST"])
def add_comment(doctype: str, docname: str, content: str):
    """Add a comment to a record, via Frappe's own Document.add_comment -
    not a new doctype invented for this."""
    _ensure_access(doctype, docname)

    text = (content or "").strip()
    if not text:
        frappe.throw(_("Write something before adding a comment."))

    doc = frappe.get_doc(doctype, docname)
    comment = doc.add_comment("Comment", text)
    return {
        "name": comment.name,
        "content": comment.content,
        "comment_email": comment.comment_email,
        "comment_by": comment.comment_by,
        "creation": comment.creation,
    }
