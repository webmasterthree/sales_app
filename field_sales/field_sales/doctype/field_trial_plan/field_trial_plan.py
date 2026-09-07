# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Field Trial Plan controller.

A trial is a rep asking to leave product with a customer for them to try -
who gets it (mirroring Field Visit's Primary/Secondary distinction), what
it is, and when it's delivered. Mirrors field_visit.py: the rep and their
territory are derived on the server, never taken from a client payload as-is.

Named "Field Trial Plan" rather than "Trial Plan" - the legacy mohan_impex
app this rebuild is replacing already ships fixtures (a workflow, property
setters, custom permissions, a client script) for a doctype called exactly
"Trial Plan". Reusing that name would have silently inherited all of that
unrelated legacy configuration onto this new doctype the next time fixtures
sync, rather than the shape actually built here.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from field_sales import scope


class FieldTrialPlan(Document):
    def validate(self):
        self.set_sales_person()
        self.set_territory()
        self.set_channel_partner()
        self.validate_visit_type()
        self.set_status()

    def before_update_after_submit(self):
        """A plain `doc.save()` on an already-submitted document - which is
        exactly what recording an attendance item does - runs this hook
        instead of `validate()` (see Document.run_before_save_methods): Frappe
        treats "still submitted, just changing an allow-on-submit field" as a
        distinct action from a normal save. `set_status` has to be reachable
        from here too, or checking off the attendance checklist would update
        the fields but never actually complete the trial."""
        self.set_status()

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
        """See field_visit.FieldVisit.set_territory for why a bare
        truthiness check on self.territory is not safe here either."""
        self.territory = scope.resolve_leaf_territory(
            self.territory, employee=self.sales_person, fallback_user=frappe.session.user
        )
        if not self.territory:
            frappe.throw(_("Give a territory for this trial."))

    # ------------------------------------------------------------ validation

    def set_channel_partner(self):
        """visit_type/channel_partner mirror the *customer's own* master-data
        classification (Customer.customer_level / custom_channel_partner) -
        see field_visit.FieldVisit.set_channel_partner for the full reasoning.
        A trial's customer is always a real Customer (unlike Field Visit,
        there's no Prospect case here), so this always applies."""
        if not self.customer:
            return
        level, channel_partner = frappe.db.get_value(
            "Customer", self.customer, ["customer_level", "custom_channel_partner"]
        ) or (None, None)
        self.visit_type = level or "Primary"
        self.channel_partner = channel_partner or None

    def validate_visit_type(self):
        """Spec: a Secondary trial (run through a channel partner) must name
        that partner. Guaranteed by set_channel_partner above for any real
        customer - this is defence in depth against a Customer record
        missing the field, same as field_visit.FieldVisit.validate_visit_type."""
        if self.visit_type == "Secondary" and not self.channel_partner:
            frappe.throw(_("A Secondary trial must have a Channel Partner."))

    # ------------------------------------------------------------ status

    def set_status(self):
        """Completed is earned, not chosen: only once the trial is actually
        submitted and every attendance item is done. A still-draft or
        partially-attended trial stays Scheduled regardless of what a client
        sends for `status` - this field is read-only on the doctype for
        exactly that reason."""
        if self.docstatus == 1 and self.sample_distributed and self.feedback_collected and self.follow_up_order:
            self.status = "Completed"
        else:
            self.status = "Scheduled"
