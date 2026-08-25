# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Product Demo controller.

Mirrors field_visit.py: the demo belongs to whichever employee is signed in
and to their own territory, both derived on the server, never taken from a
client payload as-is. Duration, like a visit's, is a measurement the server
makes from its own timestamps, not a number handed to it.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, time_diff_in_seconds

from field_sales import scope


class ProductDemo(Document):
    def validate(self):
        self.set_sales_person()
        self.set_territory()
        self.validate_party()
        self.set_duration()

    def before_submit(self):
        if not self.items:
            frappe.throw(_("Add at least one item that was demoed."))

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
        """See field_visit.FieldVisit.set_territory for why a bare truthiness
        check on self.territory is not safe here either."""
        self.territory = scope.resolve_leaf_territory(
            self.territory, employee=self.sales_person, fallback_user=frappe.session.user
        )
        if not self.territory:
            frappe.throw(_("Give a territory for this demo."))

    # ------------------------------------------------------------ validation

    def validate_party(self):
        if self.party_type == "Customer" and not self.customer:
            frappe.throw(_("Select the customer this demo was given to."))
        if self.party_type == "Prospect" and not self.prospect_name:
            frappe.throw(_("Enter a name for the prospect this demo was given to."))
        if self.party_type == "Customer":
            self.prospect_name = None
        else:
            self.customer = None
            self.customer_name = None

    def set_duration(self):
        """Derive the demo length from the server's own timestamps, never a
        number a client could send directly."""
        if not (self.started_on and self.completed_on):
            self.duration = 0
            return

        start, end = get_datetime(self.started_on), get_datetime(self.completed_on)
        if end < start:
            frappe.throw(_("Completion time cannot be earlier than the start time."))
        self.duration = time_diff_in_seconds(end, start)
