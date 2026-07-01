# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime, today


class PostDatedCheque(Document):
	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero"))

		if not self.presenting_date:
			self.presenting_date = self.cheque_date

		if not self.currency:
			self.currency = frappe.db.get_value("Company", self.company, "default_currency")

		if getdate(self.cheque_date) < getdate(self.receiving_date):
			frappe.throw(_("Cheque Date cannot be before Receiving Date"))

	def on_submit(self):
		self.db_set("status", "Held")
		_append_pdc_history(self, "Held", _("PDC received and held"))

	def on_cancel(self):
		if self.status in ("Presented", "Cleared"):
			frappe.throw(_("Cancel the linked Payment Entry before cancelling this PDC."))
		self.db_set("status", "Cancelled")
		_append_pdc_history(self, "Cancelled", _("PDC cancelled"))


def _append_pdc_history(doc, status, remarks="", payment_entry=None):
	doc = frappe.get_doc("Post Dated Cheque", doc.name)
	doc.append(
		"status_history",
		{
			"status": status,
			"changed_on": now_datetime(),
			"remarks": remarks,
			"payment_entry": payment_entry,
		},
	)
	doc.save(ignore_permissions=True)
