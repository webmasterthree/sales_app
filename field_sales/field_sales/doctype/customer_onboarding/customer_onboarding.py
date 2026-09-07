# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Customer Onboarding controller.

A rep captures a prospective outlet's details and compliance documents in the
field; a manager reviews and either approves it - which creates the real
Customer record - or rejects it. The Customer is never created by the rep
directly, and never created just by submitting the form: approval is its own
guarded action.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate

from field_sales import scope


class CustomerOnboarding(Document):
    def validate(self):
        self.set_sales_person()
        self.set_territory()
        self.validate_business_type()
        self.validate_credit_terms()
        self.validate_address()
        self.validate_duplicate()

    def before_submit(self):
        if not self.documents:
            frappe.throw(_("Attach at least one compliance document before submitting."))

    def set_sales_person(self):
        if self.sales_person:
            return
        employee = frappe.db.get_value(
            "Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
        )
        if employee:
            self.sales_person = employee

    def set_territory(self):
        self.territory = scope.resolve_leaf_territory(
            self.territory, employee=self.sales_person, fallback_user=frappe.session.user
        )
        if not self.territory:
            frappe.throw(_("Give a territory for this onboarding request."))

    def validate_business_type(self):
        if self.business_type == "Registered" and not self.gstin:
            frappe.throw(_("A registered business needs a GSTIN."))
        if self.business_type == "Unregistered":
            self.gstin = None
            self.gst_category = None

    def validate_credit_terms(self):
        if self.proposed_credit == "Credit" and not self.credit_days:
            frappe.throw(_("Give the proposed credit period in days."))
        if self.proposed_credit == "Advance":
            self.credit_days = None
            self.credit_limit = None

    def validate_address(self):
        """An outlet needs an address - either an existing Address record
        (`location`) or enough inline detail to build a new one on approval.
        Same either/or shape as Field Visit, just enforced as mandatory here
        since onboarding is how a new outlet's address is registered."""
        if self.location:
            return
        if not (self.address_line1 and self.city and self.state and self.pincode):
            frappe.throw(
                _(
                    "Give the outlet's address: either pick an existing Address, "
                    "or fill in address line 1, city, state and pincode."
                )
            )

    def validate_duplicate(self):
        """A rep with nothing stopping them can file unlimited onboarding
        requests for the same outlet. `contact_number` is the one field that
        is *always* present (it is mandatory) and identifies the person being
        onboarded regardless of business_type, so it is the natural key here
        - GSTIN is a stronger identifier when the business is registered, so
        a match on either counts as a duplicate.

        Scope decisions, in order:

        - Cross-rep, not just "your own requests": the point of the check is
          to stop the *outlet* from being onboarded twice, not to stop one
          rep from resubmitting - two different reps chasing the same outlet
          is exactly the case this needs to catch, since neither of them can
          see the other's pipeline to know it is already in flight.
        - Rejected requests do not count as duplicates: a rejection means
          that specific request was refused (bad documents, ineligible
          business, etc.), not that the outlet can never be onboarded again.
          A rep must be able to re-file after fixing whatever got it
          rejected.
        - Cancelled requests (docstatus 2) do not count either - a
          cancelled document is withdrawn, functionally the same as it never
          having been filed.
        - An *approved* request still counts as a duplicate on purpose, even
          though the spec's "duplicate KYC" language could be read as
          "don't let two pending requests collide". An approved onboarding
          already has a live Customer record; filing a fresh KYC for the
          same outlet is never the right next step for a rep who wants to
          transact with a customer that already exists - they should be
          referencing the existing Customer, not re-onboarding it. Blocking
          on Approved surfaces that mistake immediately instead of silently
          creating a second, orphaned Customer down the line.
        """
        if not self.contact_number:
            return

        or_filters = [["Customer Onboarding", "contact_number", "=", self.contact_number]]
        if self.gstin:
            or_filters.append(["Customer Onboarding", "gstin", "=", self.gstin])

        filters = [
            ["Customer Onboarding", "docstatus", "!=", 2],
            ["Customer Onboarding", "status", "!=", "Rejected"],
        ]
        if self.name:
            filters.append(["Customer Onboarding", "name", "!=", self.name])

        existing = frappe.get_all(
            "Customer Onboarding",
            filters=filters,
            or_filters=or_filters,
            fields=["name", "customer_name", "status"],
            limit=1,
        )
        if existing:
            match = existing[0]
            frappe.throw(
                _(
                    "This looks like a duplicate: {0} ({1}) is an existing, "
                    "still-active onboarding request for the same contact "
                    "number or GSTIN, with status {2}."
                ).format(
                    frappe.utils.get_link_to_form("Customer Onboarding", match.name),
                    match.customer_name,
                    match.status,
                )
            )


# ---------------------------------------------------------------- approval

# Fields native to Customer, always safe to set on a clean install.
NATIVE_CUSTOMER_FIELDS = {
    "customer_name": "customer_name",
    "customer_group": "customer_group",
    "territory": "territory",
    "market_segment": "market_segment",
}

# mohan_impex adds these as *mandatory* custom fields on Customer, which is
# itself one of the portability defects in that app - a clean field_sales
# install has none of them. Populated only when present, and only ever as
# optional data; nothing here should ever be made mandatory again.
LEGACY_CUSTOMER_FIELDS = {
    "business_type": "business_type",
    "gst_category": "gst_category",
}


def _default_customer_group() -> str | None:
    """A real, non-group Customer Group.

    ERPNext's setup wizard sets a *system default* of "All Customer Groups"
    for the fieldname "customer_group" - and `frappe.new_doc` auto-populates
    any field whose name matches a system default, so a freshly created
    Customer Onboarding already carries that value even though nothing in
    this app set it. It is itself a group and is rejected by Customer's own
    validation, so it is never usable as-is.
    """
    return frappe.db.get_value("Customer Group", {"is_group": 0}, "name")


def _resolve_customer_group(value: str | None) -> str | None:
    if value and not frappe.db.get_value("Customer Group", value, "is_group"):
        return value
    return _default_customer_group()


def _build_customer(doc: "Document") -> "Document":
    customer = frappe.new_doc("Customer")
    customer.customer_type = "Company"

    meta = customer.meta
    for src, dest in NATIVE_CUSTOMER_FIELDS.items():
        if meta.has_field(dest):
            value = doc.get(src)
            if dest == "customer_group":
                value = _resolve_customer_group(value)
            customer.set(dest, value)
    for src, dest in LEGACY_CUSTOMER_FIELDS.items():
        if meta.has_field(dest):
            customer.set(dest, doc.get(src))
    if meta.has_field("gstin"):
        customer.gstin = doc.gstin
    if meta.has_field("pan"):
        customer.pan = doc.pan

    # The approver's own role need not carry Customer create permission - the
    # server, not the manager's desk role, is what authorises this write.
    # `_require_approver` is the actual gate.
    customer.flags.ignore_mandatory = True
    customer.insert(ignore_permissions=True)
    return customer


def _build_address(customer_name: str, doc: "Document") -> "Document":
    """A brand-new outlet's Address, built from the inline fields captured
    at onboarding - this IS how a new address gets registered, so it must
    not require one to already exist."""
    addr = frappe.new_doc("Address")
    addr.address_title = doc.customer_name
    addr.address_type = "Billing"
    addr.address_line1 = doc.address_line1
    addr.address_line2 = doc.address_line2
    # On this site (india_compliance installed) several Address fields that
    # look like free text on a clean Frappe install - city, district - are
    # actually Links to India-specific master doctypes (City, District). Our
    # own inline fields stay plain Data, since a rep in the field cannot be
    # expected to know whether a master record exists yet for the place
    # they're standing in. Only carry a value across when it actually
    # resolves as a Link target; a value that doesn't resolve is dropped
    # rather than failing the whole approval over an optional field.
    for fieldname, value in (("city", doc.city), ("district", doc.district)):
        if not value:
            continue
        field = addr.meta.get_field(fieldname)
        if not field:
            continue
        if field.fieldtype == "Link" and not frappe.db.exists(field.options, value):
            continue
        addr.set(fieldname, value)
    addr.state = doc.state
    addr.pincode = doc.pincode
    addr.append("links", {"link_doctype": "Customer", "link_name": customer_name})
    addr.flags.ignore_mandatory = True
    addr.insert(ignore_permissions=True)
    return addr


def _link_contact_and_address(customer_name: str, doc: "Document") -> None:
    if doc.location:
        addr = frappe.get_doc("Address", doc.location)
        if not any(l.link_doctype == "Customer" and l.link_name == customer_name
                  for l in addr.links):
            addr.append("links", {"link_doctype": "Customer", "link_name": customer_name})
            addr.save(ignore_permissions=True)
        frappe.db.set_value("Customer", customer_name, "customer_primary_address",
                            doc.location, update_modified=False)
    elif doc.address_line1:
        addr = _build_address(customer_name, doc)
        frappe.db.set_value("Customer", customer_name, "customer_primary_address",
                            addr.name, update_modified=False)

    if doc.contact_number:
        contact = frappe.new_doc("Contact")
        contact.first_name = doc.contact_person or doc.customer_name
        contact.append("phone_nos", {"phone": doc.contact_number, "is_primary_mobile_no": 1})
        contact.append("links", {"link_doctype": "Customer", "link_name": customer_name})
        contact.flags.ignore_mandatory = True
        contact.insert(ignore_permissions=True)
        frappe.db.set_value("Customer", customer_name, "customer_primary_contact",
                            contact.name, update_modified=False)
        frappe.db.set_value("Customer", customer_name, "mobile_no", doc.contact_number,
                            update_modified=False)


APPROVER_ROLES = {"Sales Manager", "System Manager"}


def _require_approver():
    """A rep can submit their own request - that only makes it Pending.

    Approving it creates real master data, so it needs a role the rep does
    not hold. Checking the doctype's own "submit" permission is not enough:
    the rep already has that, on their own document.
    """
    if not (APPROVER_ROLES & set(frappe.get_roles())):
        raise frappe.PermissionError(
            frappe._("Only a manager may decide on an onboarding request.")
        )


@frappe.whitelist()
def approve_onboarding(name: str, remarks: str | None = None) -> dict:
    """Approve an onboarding request, creating the Customer record.

    A separate, role-checked action rather than a status field a writer could
    flip - the original let anyone who could edit the document mark it
    approved, which is the same class of gap as an order pricing itself.
    """
    doc = frappe.get_doc("Customer Onboarding", name)
    doc.check_permission("read")
    _require_approver()

    if doc.docstatus != 1:
        frappe.throw(_("Submit the onboarding request before approving it."))
    if doc.status != "Pending":
        frappe.throw(_("This request has already been {0}.").format(doc.status.lower()))

    customer = _build_customer(doc)
    _link_contact_and_address(customer.name, doc)

    doc.db_set("customer", customer.name)
    doc.db_set("status", "Approved")
    doc.db_set("decided_on", nowdate())
    if remarks:
        doc.db_set("decision_remarks", remarks)

    return {"name": doc.name, "status": "Approved", "customer": customer.name}


@frappe.whitelist()
def reject_onboarding(name: str, remarks: str) -> dict:
    doc = frappe.get_doc("Customer Onboarding", name)
    doc.check_permission("read")
    _require_approver()

    if doc.docstatus != 1:
        frappe.throw(_("Submit the onboarding request before deciding on it."))
    if doc.status != "Pending":
        frappe.throw(_("This request has already been {0}.").format(doc.status.lower()))
    if not (remarks or "").strip():
        frappe.throw(_("Say why the request is being rejected."))

    doc.db_set("status", "Rejected")
    doc.db_set("decided_on", nowdate())
    doc.db_set("decision_remarks", remarks.strip())

    return {"name": doc.name, "status": "Rejected"}
