# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FieldSalesBranding(Document):
	def validate(self):
		self.validate_icon_is_public()

	def validate_icon_is_public(self):
		# The manifest/favicon/push-icon endpoints (api/branding.py) are all
		# allow_guest, so a private file - one whose URL 404s for anyone not
		# logged in as the uploader - would silently break the very things
		# this field exists for. A public file's URL always starts with
		# /files/; a private one starts with /private/files/.
		if self.app_icon and self.app_icon.startswith("/private/files/"):
			frappe.throw(
				_("The app icon must be a public file, not a private one - "
				  "re-upload it and make sure \"Private\" is unchecked.")
			)
