# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.document import Document


class City(Document):
	def before_insert(self):
		self.autoname()

	def autoname(self):
		district_info = frappe.db.get_value("District", self.district, ["district", "state"], as_dict=True)
		if not district_info:
			frappe.throw("Please select a valid District before saving the City")

		state_info = frappe.db.get_value("State", district_info.state, ["state"], as_dict=True)
		if not state_info:
			frappe.throw("State not found for selected District")

		state_code = make_slug(state_info.state)
		district_code = make_slug(district_info.district)
		city_code = make_slug(self.city)

		self.name = f"{state_code}-{district_code}-{city_code}"


def make_slug(text):
	"""Return uppercase alphanumeric slug (no spaces or symbols)."""
	return re.sub(r"[^A-Z0-9]", "", text.upper())
