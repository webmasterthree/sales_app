# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Demo Evaluation controller.

The scorecard is the product's differentiator, so it is worth validating
properly. The original stored a rating and a measurement in untyped columns
and never checked which one belonged to which parameter, so an evaluation
could record "Excellent" against a parameter measured in minutes.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

RATING_TYPE = "Rating"


class DemoEvaluation(Document):
    def validate(self):
        self.validate_lines()
        self.validate_outcome()
        self.link_to_demo_item()

    def validate_lines(self):
        for row in self.parameters or []:
            value_type = row.value_type or frappe.db.get_value(
                "Demo Parameter", row.parameter, "value_type"
            )
            row.value_type = value_type

            if value_type == RATING_TYPE:
                if not row.rating:
                    frappe.throw(
                        _("Row {0}: give a rating for {1}.").format(row.idx, row.parameter)
                    )
                # a measurement against a judgement parameter is meaningless
                row.value = 0
            else:
                if row.value in (None, ""):
                    frappe.throw(
                        _("Row {0}: give a measured value for {1}.").format(
                            row.idx, row.parameter
                        )
                    )
                row.rating = None

            requires_remarks = frappe.db.get_value(
                "Demo Parameter", row.parameter, "requires_remarks"
            )
            if cint(requires_remarks) and not (row.remarks or "").strip():
                frappe.throw(
                    _("Row {0}: {1} needs remarks.").format(row.idx, row.parameter)
                )

    def validate_outcome(self):
        if self.order_received:
            # an order makes the "why not" answer nonsense
            self.no_order_reason = None
        elif self.outcome == "Unsuccessful" and not self.no_order_reason:
            frappe.throw(_("Say why the demo did not produce an order."))

    def link_to_demo_item(self):
        """Point the demo's line at this evaluation, so the two agree."""
        if not (self.product_demo and self.item_code):
            return
        rows = frappe.get_all(
            "Product Demo Item",
            filters={"parent": self.product_demo, "item_code": self.item_code},
            pluck="name",
        )
        for row in rows:
            frappe.db.set_value(
                "Product Demo Item", row, "evaluation", self.name, update_modified=False
            )


def summarise(product_demo: str) -> dict:
    """How a demo went, across all its evaluated products."""
    evaluations = frappe.get_all(
        "Demo Evaluation",
        filters={"product_demo": product_demo},
        fields=["name", "item_code", "outcome", "order_received"],
    )
    successful = sum(1 for e in evaluations if e.outcome == "Successful")
    ordered = sum(1 for e in evaluations if cint(e.order_received))
    return {
        "evaluated": len(evaluations),
        "successful": successful,
        "orders": ordered,
        "success_rate": round(successful / len(evaluations) * 100, 1) if evaluations else 0.0,
        "evaluations": evaluations,
    }
