# Copyright (c) 2026, Aakvatech and contributors
# License: MIT

import frappe
from frappe import _
from frappe.utils import getdate, today


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("PDC"), "fieldname": "name", "fieldtype": "Link", "options": "Post Dated Cheque", "width": 140},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
		{"label": _("Agreement"), "fieldname": "agreement", "fieldtype": "Link", "options": "Agreement", "width": 140},
		{"label": _("Cheque No"), "fieldname": "cheque_no", "fieldtype": "Data", "width": 120},
		{"label": _("Cheque Date"), "fieldname": "cheque_date", "fieldtype": "Date", "width": 110},
		{"label": _("Presenting Date"), "fieldname": "presenting_date", "fieldtype": "Date", "width": 120},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 140},
	]


def get_data(filters):
	conditions = {"docstatus": 1}
	if filters.get("company"):
		conditions["company"] = filters.get("company")
	if filters.get("status"):
		conditions["status"] = filters.get("status")
	else:
		conditions["status"] = ["in", ["Held", "Presented"]]

	if filters.get("from_date"):
		conditions["presenting_date"] = [">=", filters.get("from_date")]
	if filters.get("to_date"):
		if "presenting_date" in conditions:
			conditions["presenting_date"] = [
				"between",
				[filters.get("from_date") or "1900-01-01", filters.get("to_date")],
			]
		else:
			conditions["presenting_date"] = ["<=", filters.get("to_date")]

	return frappe.get_all(
		"Post Dated Cheque",
		filters=conditions,
		fields=[
			"name",
			"customer",
			"agreement",
			"cheque_no",
			"cheque_date",
			"presenting_date",
			"amount",
			"status",
			"company",
		],
		order_by="presenting_date asc, cheque_date asc",
	)
