# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Field Visit controller.

A visit is a timed, located event. The rep checks in on arrival and out on
leaving; the duration and both timestamps come from the server, and the
position is checked against the outlet rather than taken on trust.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, get_datetime, now_datetime, time_diff_in_seconds

from field_sales import geo, scope


class FieldVisit(Document):
    def validate(self):
        self.set_sales_person()
        self.set_territory()
        self.validate_party()
        self.set_channel_partner()
        self.validate_visit_type()
        self.validate_outcome()
        self.set_duration()

    def before_submit(self):
        if not self.check_in:
            frappe.throw(_("Check in before submitting the visit."))
        if not self.check_out:
            frappe.throw(_("Check out before submitting the visit."))

    # ------------------------------------------------------------ defaults

    def set_sales_person(self):
        if self.sales_person:
            return
        employee = frappe.db.get_value(
            "Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
        )
        if employee:
            self.sales_person = employee

    def set_territory(self):
        """Fall back to the visiting employee's own territory.

        Uses scope.resolve_leaf_territory rather than a bare truthiness check:
        Frappe pre-fills a new document's `territory` from a system default of
        "All Territories" before validate() ever runs, so `if self.territory`
        is already true on every fresh draft regardless of what the client
        sent - see resolve_leaf_territory's docstring for the full mechanism.
        """
        self.territory = scope.resolve_leaf_territory(
            self.territory, employee=self.sales_person, fallback_user=frappe.session.user
        )
        if not self.territory:
            frappe.throw(_("Give a territory for this visit."))

    # ------------------------------------------------------------ validation

    def validate_party(self):
        if self.party_type == "Customer" and not self.customer:
            frappe.throw(_("Select the customer that was visited."))
        if self.party_type == "Prospect" and not self.prospect_name:
            frappe.throw(_("Enter a name for the prospect that was visited."))
        if self.party_type == "Customer":
            self.prospect_name = None
        else:
            self.customer = None
            self.customer_name = None

    def set_channel_partner(self):
        """visit_type/channel_partner mirror the *customer's own* master-data
        classification (Customer.customer_level / custom_channel_partner,
        both real fields added by the org's existing customer master - see
        fmcg_cp's customer.json customisation) rather than something a rep
        decides fresh on every visit. A customer that is itself Secondary is
        always reached through the same channel partner regardless of which
        visit it is; letting a rep pick a different one per visit would let
        the same customer end up attributed to different channel partners
        across visits, which the master data already has one answer for.

        Only Customer visits have a record to derive this from - a Prospect
        has no Customer master yet, so visit_type/channel_partner stay
        whatever the rep (or create_visit's caller) actually set for those,
        the same as before this existed.
        """
        if self.party_type != "Customer" or not self.customer:
            return
        level, channel_partner = frappe.db.get_value(
            "Customer", self.customer, ["customer_level", "custom_channel_partner"]
        ) or (None, None)
        self.visit_type = level or "Primary"
        self.channel_partner = channel_partner or None

    def validate_visit_type(self):
        """Spec: "For Secondary visit, channel partner is required."

        For a Customer visit this is now guaranteed by set_channel_partner
        (a Secondary customer always has a channel partner - enforced on the
        Customer record itself via its own mandatory_depends_on). This guard
        still matters for a Prospect visit, where visit_type/channel_partner
        are still rep-supplied - see api/field_visit.py's WRITABLE_FIELDS -
        and for defence in depth against a Customer record missing the field.
        """
        if self.visit_type == "Secondary" and not self.channel_partner:
            frappe.throw(_("A Secondary visit must have a Channel Partner."))

    def validate_outcome(self):
        if self.order_status == "Without Order" and not self.reason:
            frappe.throw(_("Give a reason why the visit did not produce an order."))
        if self.order_status == "With Order":
            self.reason = None

    def set_duration(self):
        """Derive the visit length. Never trust a duration sent by a client."""
        if not (self.check_in and self.check_out):
            self.duration = 0
            return

        start, end = get_datetime(self.check_in), get_datetime(self.check_out)
        if end < start:
            frappe.throw(_("Check-out cannot be earlier than check-in."))
        self.duration = time_diff_in_seconds(end, start)


# ---------------------------------------------------------------- check in / out


@frappe.whitelist()
def check_in(field_visit: str, latitude=None, longitude=None,
             captured_address: str | None = None) -> dict:
    """Stamp arrival, after checking the rep is actually at the outlet.

    The timestamp is the server's. The position is compared against the
    outlet's own stored coordinates, not against a destination supplied by the
    caller - which is what made the original check bypassable. A real GPS fix
    is mandatory here (not just preferred) - geofencing is always on, and a
    visit that can be checked in without ever fetching a position would let a
    rep skip it entirely, submit included, since submit only requires
    check-in and check-out to exist.
    """
    doc = frappe.get_doc("Field Visit", field_visit)
    doc.check_permission("write")

    if doc.docstatus != 0:
        frappe.throw(_("This visit is no longer a draft."))
    if doc.check_in:
        frappe.throw(_("This visit has already been checked in."))
    if not geo.is_valid_position(latitude, longitude):
        frappe.throw(_("Turn on location and try again - a GPS fix is required to check in."))

    fence = geo.evaluate(doc.location, latitude, longitude)
    if fence["blocked"]:
        frappe.throw(fence["message"], frappe.ValidationError)

    doc.check_in = now_datetime()
    if geo.is_valid_position(latitude, longitude):
        doc.check_in_latitude = flt(latitude)
        doc.check_in_longitude = flt(longitude)
    if captured_address:
        doc.captured_address = captured_address

    doc.check_in_distance = fence["distance"]
    doc.geofence_status = fence["status"]
    doc.save()

    return {
        "check_in": doc.check_in,
        "geofence": fence["status"],
        "distance": fence["distance"],
        "message": fence["message"],
    }


@frappe.whitelist()
def check_out(field_visit: str, latitude=None, longitude=None) -> dict:
    """Stamp departure and derive the duration."""
    doc = frappe.get_doc("Field Visit", field_visit)
    doc.check_permission("write")

    if doc.docstatus != 0:
        frappe.throw(_("This visit is no longer a draft."))
    if not doc.check_in:
        frappe.throw(_("Check in before checking out."))
    if doc.check_out:
        frappe.throw(_("This visit has already been checked out."))

    doc.check_out = now_datetime()
    if geo.is_valid_position(latitude, longitude):
        doc.check_out_latitude = flt(latitude)
        doc.check_out_longitude = flt(longitude)
    doc.save()

    return {"check_out": doc.check_out, "duration": doc.duration}
