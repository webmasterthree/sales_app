# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Journey Plan controller.

A journey plan is a rep's proposed travel route for a day: one or more
trips (legs), each with a mode of travel and the customers it covers. It
starts as a draft the rep can still edit, and becomes an approved plan of
record once submitted - mirroring Field Visit's draft/submitted lifecycle
rather than introducing a separate workflow mechanism for the same shape
of problem.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from field_sales import scope


class JourneyPlan(Document):
    def validate(self):
        self.set_sales_person()
        self.set_territory()
        self.validate_trips()

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
        """Fall back to the rep's own territory - see Field Visit's
        set_territory for why this can't be a bare truthiness check."""
        self.territory = scope.resolve_leaf_territory(
            self.territory, employee=self.sales_person, fallback_user=frappe.session.user
        )
        if not self.territory:
            frappe.throw(_("Give a territory for this journey plan."))

    # ------------------------------------------------------------ validation

    def validate_trips(self):
        if not self.trips:
            frappe.throw(_("Add at least one trip to the journey plan."))
        for row in self.trips:
            if row.same_as_from_address:
                row.travel_to_state = row.travel_state_from
                row.travel_to_district = row.travel_from_district
                row.travel_to_city = row.travel_from_city
